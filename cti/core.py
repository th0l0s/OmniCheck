"""
core.py — shared primitives for the whole app.

Everything the sources and the scheduler need that is NOT source-specific:
  - TTLCache         in-process cache with stale-while-revalidate
  - safe_gather      asyncio.gather that never lets one failure sink the batch
  - CircuitBreaker   trip-after-N-failures guard around a flaky upstream
  - Ctx              the object handed to every source.fetch()
  - setup_logging    one logging config for the process

No Redis, no Prometheus, no external cache: the deploy is single-host (CLAUDE.md).
Reintroduce a shared store only when there is more than one process to share with.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, Awaitable, Callable, Optional

import httpx

log = logging.getLogger("cti.core")


# ── logging ─────────────────────────────────────────────────────────────────

def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers[:] = [handler]
    # httpx/httpcore are chatty at DEBUG — every request prints a dozen lines.
    for noisy in ("httpx", "httpcore", "httpcore.http11", "httpcore.connection"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── cache ───────────────────────────────────────────────────────────────────

class TTLCache:
    """In-memory store. Thread-safe on CPython (GIL-atomic dict ops).

    Entry = (set_at, ttl, value). stale_ok lets a caller serve an expired value
    while a refresh runs in the background.
    """

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, float, Any]] = {}

    def get(self, key: str, stale_ok: bool = False) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        set_at, ttl, val = entry
        if time.monotonic() - set_at > ttl:
            if stale_ok:
                return val
            return None
        return val

    def set(self, key: str, value: Any, ttl: float) -> None:
        self._store[key] = (time.monotonic(), float(ttl), value)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def age(self, key: str) -> Optional[float]:
        entry = self._store.get(key)
        if entry is None:
            return None
        return round(time.monotonic() - entry[0], 1)

    def is_stale(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return True
        set_at, ttl, _ = entry
        return time.monotonic() - set_at > ttl


# ── concurrency helpers ───────────────────────────────────────────────────────

async def safe_gather(*aws: Awaitable, default: Any = None) -> list:
    """gather() that returns `default` in place of any awaitable that raised,
    instead of propagating the first exception. Failures are logged, not fatal."""
    results = await asyncio.gather(*aws, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, Exception):
            log.warning("safe_gather: task failed: %s", r)
            out.append(default)
        else:
            out.append(r)
    return out


class CircuitBreaker:
    """Open after `threshold` consecutive failures; stay open for `reset` seconds.

    While open, call() short-circuits and raises without touching the upstream,
    so a dead source stops wasting time on every scheduler tick.
    """

    def __init__(self, threshold: int = 5, reset: float = 120.0) -> None:
        self.threshold = threshold
        self.reset = reset
        self._failures = 0
        self._opened_at = 0.0

    @property
    def open(self) -> bool:
        if self._failures < self.threshold:
            return False
        if time.monotonic() - self._opened_at >= self.reset:
            return False  # half-open: allow one trial call
        return True

    async def call(self, coro: Callable[[], Awaitable], name: str = "") -> Any:
        if self.open:
            raise RuntimeError(f"circuit open for {name or 'upstream'}")
        try:
            result = await coro()
        except Exception:
            self._failures += 1
            if self._failures == self.threshold:
                self._opened_at = time.monotonic()
                log.warning("circuit tripped for %s after %d failures", name, self._failures)
            raise
        self._failures = 0
        return result


# ── manual-refresh guard ────────────────────────────────────────────────────

class RefreshGate:
    """Throttle manual refreshes: a per-source cooldown plus a per-source lock so
    two manual refreshes of the same source can't run (or stampede upstream) at
    once. Raises HTTP-mapped errors the route turns into 429/409."""

    def __init__(self, min_interval_s: float = 60.0) -> None:
        self.min_interval_s = min_interval_s
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock_for(self, source_id: str) -> asyncio.Lock:
        return self._locks.setdefault(source_id, asyncio.Lock())

    def check(self, source_id: str) -> None:
        """Raise (429/409) if a manual refresh is not allowed right now."""
        from fastapi import HTTPException
        if self.lock_for(source_id).locked():
            raise HTTPException(409, "refresh already running")
        elapsed = time.monotonic() - self._last.get(source_id, 0.0)
        if elapsed < self.min_interval_s:
            raise HTTPException(429, f"refresh cooldown: retry in {int(self.min_interval_s - elapsed)}s")

    def mark(self, source_id: str) -> None:
        self._last[source_id] = time.monotonic()


# ── source context ────────────────────────────────────────────────────────────

class Ctx:
    """Handed to every source.fetch(). Carries the shared HTTP client and cache
    so individual sources don't each spin up their own."""

    def __init__(self, client: httpx.AsyncClient, cache: TTLCache) -> None:
        self.client = client
        self.cache = cache
