"""
main.py — the one FastAPI app. Routes are generic; sources are data, not code.

  GET /                     the single dashboard (static/index.html)
  GET /api/sources          registry + schema() of every source (drives the UI tabs)
  GET /api/health           per-source {ok, last_fetch, age_s, error} + process status
  GET /api/data/{id}        the latest cached, parsed payload for one source
  POST /api/refresh/{id}    force an immediate refresh of one source

Adding a source = drop a file in cti/sources/ and a tab appears. No new route,
no new HTML. That is the whole point of Plan B.
"""
from __future__ import annotations

import logging
import platform
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, config, registry, scheduler, store
from .auth import require_api_key
from .core import Ctx, RefreshGate, TTLCache, setup_logging

log = logging.getLogger("cti.main")
_STARTED = time.time()
_GATE = RefreshGate(min_interval_s=60.0)

_STATIC = Path(__file__).resolve().parent / "static"
_DESIGN = _STATIC / "icons"

CFG = config.load()
setup_logging(bool(CFG.get("debug")))

STATES = registry.discover()
CACHE = TTLCache()
_USER_AGENT = "CTI-Sentinel/%s" % __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=8.0),
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    )
    ctx = Ctx(client=client, cache=CACHE)
    # warm the cache from disk so the dashboard isn't empty right after a restart
    warmed = 0
    for sid, state in STATES.items():
        saved = store.load_source(sid)
        if saved and saved.get("data") is not None:
            CACHE.set(sid, saved["data"], ttl=state.interval * 3)
            state.last_fetch = saved.get("fetched_at")
            warmed += 1
    tasks = scheduler.start(STATES, CFG, ctx)
    log.info("CTI v%s up — %d sources registered, %d warmed from disk", __version__, len(STATES), warmed)
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await client.aclose()


app = FastAPI(title="CTI Sentinel", version=__version__, lifespan=lifespan)

if _STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
if _DESIGN.is_dir():
    app.mount("/icons", StaticFiles(directory=str(_DESIGN)), name="icons")


@app.get("/", include_in_schema=False)
async def index():
    idx = _STATIC / "index.html"
    if idx.is_file():
        return FileResponse(str(idx))
    return JSONResponse({"status": "ok", "version": __version__, "docs": "/docs"})


@app.get("/api/sources")
async def api_sources():
    """Registry + each source's schema() — the dashboard builds its tabs from this."""
    out = []
    for s in STATES.values():
        try:
            sch = s.module.schema()
        except Exception as exc:
            sch = {"title": s.name, "error": str(exc)}
        out.append({**s.health(), "schema": sch})
    return {"version": __version__, "count": len(out), "sources": out}


@app.get("/api/health")
async def api_health():
    sources = [s.health() for s in STATES.values()]
    healthy = sum(1 for s in sources if s["ok"])
    return {
        "status": "ok",
        "version": __version__,
        "sources_total": len(sources),
        "sources_ok": healthy,
        "sources": sources,
    }


@app.get("/api/status")
async def api_status():
    """Diagnostics for the status/about page: runtime info + config/runtime issues."""
    config_issues, runtime_errors = [], []
    sources = []
    for s in STATES.values():
        sources.append({
            "id": s.id, "name": s.name, "enabled": s.enabled, "ok": s.ok,
            "interval": s.interval, "last_fetch": s.last_fetch, "error": s.last_error,
            "requires": s.requires,
        })
        if not s.enabled and s.last_error and "missing config" in (s.last_error or ""):
            config_issues.append({"source": s.id, "detail": s.last_error})
        elif s.enabled and not s.ok and s.last_error:
            runtime_errors.append({"source": s.id, "detail": s.last_error})
    up = int(time.time() - _STARTED)
    return {
        "app": "CTI Sentinel",
        "version": __version__,
        "debug": bool(CFG.get("debug")),
        "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "uptime_s": up,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "host": CFG.get("host", "0.0.0.0"),
        "port": CFG.get("port", 8000),
        "sources_total": len(sources),
        "sources_ok": sum(1 for s in sources if s["ok"]),
        "config_issues": config_issues,
        "runtime_errors": runtime_errors,
        "sources": sources,
    }


@app.get("/api/data/{source_id}")
async def api_data(source_id: str):
    state = STATES.get(source_id)
    if state is None:
        raise HTTPException(404, f"unknown source: {source_id}")
    data = CACHE.get(source_id, stale_ok=True)
    return {
        "id": source_id,
        "name": state.name,
        "ok": state.ok,
        "stale": CACHE.is_stale(source_id),
        "age_s": CACHE.age(source_id),
        "last_fetch": state.last_fetch,
        "error": state.last_error,
        "data": data,
    }


class _TargetsIn(BaseModel):
    add: list[str] = []
    remove: list[str] = []


@app.get("/api/targets")
async def api_targets_get():
    """Current watchlists from assets.yaml."""
    from . import targets as tgt
    data = tgt.load()
    return {"ips": data["ips"], "domains": data["domains"],
            "targets": data["ips"] + data["domains"]}


@app.post("/api/targets")
async def api_targets_post(payload: _TargetsIn):
    """Add or remove IPs/domains from assets.yaml. No API key required."""
    from . import targets as tgt
    try:
        data = tgt.load()
        ips = set(data["ips"])
        domains = set(data["domains"])
        for t in payload.add:
            t = t.strip()
            if not t:
                continue
            if tgt.classify(t) == "ip":
                ips.add(t)
            else:
                domains.add(t)
        for t in payload.remove:
            t = t.strip()
            ips.discard(t)
            domains.discard(t)
        tgt.save(sorted(ips), sorted(domains))
        return {"ok": True, "ips": sorted(ips), "domains": sorted(domains),
                "targets": sorted(ips) + sorted(domains)}
    except Exception as exc:
        log.exception("targets update failed")
        raise HTTPException(400, f"Could not update targets: {exc}")


@app.post("/api/refresh/{source_id}")
async def api_refresh(source_id: str, _: None = Depends(require_api_key)):
    """Force an out-of-band refresh. Requires X-API-Key; rate-limited + locked
    per source so it can't stampede the upstream or spend quota repeatedly."""
    state = STATES.get(source_id)
    if state is None:
        raise HTTPException(404, f"unknown source: {source_id}")
    _GATE.check(source_id)
    _GATE.mark(source_id)
    async with _GATE.lock_for(source_id):
        client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0),
                                   follow_redirects=True, headers={"User-Agent": _USER_AGENT})
        ctx = Ctx(client=client, cache=CACHE)
        try:
            await scheduler.refresh_once(state, CFG, ctx)
        finally:
            await client.aclose()
    return {"id": source_id, "ok": state.ok, "error": state.last_error}
