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
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config, registry, scheduler
from .core import Ctx, TTLCache, setup_logging

log = logging.getLogger("cti.main")

_STATIC = Path(__file__).resolve().parent / "static"
_DESIGN = Path(__file__).resolve().parent.parent / "design"

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
    tasks = scheduler.start(STATES, CFG, ctx)
    log.info("CTI v%s up — %d sources registered", __version__, len(STATES))
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


@app.post("/api/refresh/{source_id}")
async def api_refresh(source_id: str):
    """Force an out-of-band refresh. Never blocks the caller beyond the fetch."""
    state = STATES.get(source_id)
    if state is None:
        raise HTTPException(404, f"unknown source: {source_id}")
    client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0),
                               follow_redirects=True, headers={"User-Agent": _USER_AGENT})
    ctx = Ctx(client=client, cache=CACHE)
    from .core import CircuitBreaker
    try:
        await scheduler._refresh(state, CFG, ctx, CircuitBreaker(threshold=99))
    finally:
        await client.aclose()
    return {"id": source_id, "ok": state.ok, "error": state.last_error}
