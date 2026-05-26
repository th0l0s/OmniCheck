import asyncio
import time

import pytest

from cti.core import CircuitBreaker, RefreshGate, TTLCache, safe_gather


def test_ttlcache_set_get_expiry():
    c = TTLCache()
    c.set("k", 123, ttl=10)
    assert c.get("k") == 123
    assert c.is_stale("k") is False
    # expire
    c.set("k", 123, ttl=0.01)
    time.sleep(0.02)
    assert c.get("k") is None          # expired, no stale_ok
    assert c.get("k", stale_ok=True) == 123  # still served as stale
    assert c.is_stale("k") is True


def test_ttlcache_missing_key():
    c = TTLCache()
    assert c.get("nope") is None
    assert c.age("nope") is None
    assert c.is_stale("nope") is True


@pytest.mark.asyncio
async def test_circuitbreaker_opens_and_resets():
    cb = CircuitBreaker(threshold=2, reset=0.05)

    async def boom():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(boom, name="t")
    assert cb.open is True                      # tripped after 2 failures
    with pytest.raises(RuntimeError, match="circuit open"):
        await cb.call(boom, name="t")
    time.sleep(0.06)
    assert cb.open is False                      # half-open after reset window


@pytest.mark.asyncio
async def test_safe_gather_isolates_failures():
    async def ok():
        return 1

    async def bad():
        raise ValueError("nope")

    res = await safe_gather(ok(), bad(), ok(), default="X")
    assert res == [1, "X", 1]


@pytest.mark.asyncio
async def test_refreshgate_cooldown_and_lock():
    from fastapi import HTTPException
    g = RefreshGate(min_interval_s=60)
    g.check("s")          # first call ok
    g.mark("s")
    with pytest.raises(HTTPException) as e:
        g.check("s")      # cooldown active
    assert e.value.status_code == 429
