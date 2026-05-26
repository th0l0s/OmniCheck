"""
scheduler.py — the single background loop that refreshes every source.

One asyncio task per source. Each loop: respect the source's interval, run
fetch()+parse() under a circuit breaker, store the result in the cache keyed by
source id, and update its health state. A source that fails degrades to
ok=False with last_error set — it never takes the process down, and a previously
cached value is still served (stale-while-revalidate).

This replaces the 6 systemd units + per-service background loops with 30-odd
lines, exactly as the review asked.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .config import source_cfg
from .core import Ctx, CircuitBreaker, TTLCache
from .registry import SourceState

log = logging.getLogger("cti.scheduler")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _refresh(state: SourceState, cfg: dict, ctx: Ctx, breaker: CircuitBreaker) -> None:
    scfg = source_cfg(cfg, state.id)
    try:
        raw = await breaker.call(lambda: state.module.fetch(scfg, ctx), name=state.id)
        data = state.module.parse(raw)
        ctx.cache.set(state.id, data, ttl=state.interval * 3)  # keep servable past one miss
        state.ok = True
        state.last_error = None
        state.last_fetch = _now()
        log.info("source %s refreshed", state.id)
    except Exception as exc:
        state.ok = False
        state.last_error = str(exc)[:300]
        log.warning("source %s refresh failed: %s", state.id, exc)
    state.age_s = ctx.cache.age(state.id)


async def _loop(state: SourceState, cfg: dict, ctx: Ctx) -> None:
    breaker = CircuitBreaker(threshold=4, reset=max(60.0, state.interval))
    scfg = source_cfg(cfg, state.id)
    interval = int(scfg.get("interval", state.interval))
    # small stagger so 8 sources don't all hammer upstreams on the same tick
    await asyncio.sleep(1.0)
    while True:
        await _refresh(state, cfg, ctx, breaker)
        await asyncio.sleep(interval)


def _should_run(state: SourceState, cfg: dict) -> bool:
    scfg = source_cfg(cfg, state.id)
    if not scfg.get("enabled", True):
        state.enabled = False
        state.last_error = "disabled in config"
        return False
    missing = [k for k in state.requires if not scfg.get(k)]
    if missing:
        state.enabled = False
        state.last_error = f"missing config: {', '.join(missing)}"
        log.info("source %s skipped (%s)", state.id, state.last_error)
        return False
    return True


def start(states: dict[str, SourceState], cfg: dict, ctx: Ctx) -> list[asyncio.Task]:
    """Spawn one refresh loop per runnable source. Returns the task handles."""
    tasks: list[asyncio.Task] = []
    for state in states.values():
        if _should_run(state, cfg):
            tasks.append(asyncio.create_task(_loop(state, cfg, ctx), name=f"refresh:{state.id}"))
    log.info("scheduler started: %d/%d sources active", len(tasks), len(states))
    return tasks
