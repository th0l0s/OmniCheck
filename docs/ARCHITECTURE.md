# OmniCheck / CTI Sentinel — How the system works

One package (`cti/`), one process, one dashboard. Antirez-style: few files,
explicit state, minimal dependencies, a source can fail without taking the
process down.

## Data flow

```
config.yaml ─┐
             ▼
        registry.discover()         scans cti/sources/, registers every module
             │                       exposing ID/NAME/INTERVAL/fetch/parse/schema
             ▼
        scheduler.start()           one asyncio loop per source
             │  every INTERVAL:
             │    raw  = await source.fetch(cfg, ctx)     # pull upstream
             │    data = source.parse(raw)                # normalise to rows/summary
             │    cache.set(id, data)                     # in-process TTLCache
             │    store.save_source(id, data)             # persist to state/cache/
             ▼
        main.py (FastAPI)           generic routes serve the cache
             │
             ▼
        static/index.html           one dashboard; tabs/panels built from schema()
```

On startup the cache is **warmed from `state/cache/`** so the dashboard isn't
empty right after a restart, then live refreshes overwrite it.

## The source contract

A file in `cti/sources/` becomes a source if it defines:

| symbol | meaning |
|---|---|
| `ID` | unique slug |
| `NAME` | display name |
| `INTERVAL` | default refresh cadence (seconds) |
| `REQUIRES` | (optional) config keys that must be truthy, else the source is skipped |
| `async fetch(cfg, ctx)` | pull from upstream; `ctx.client` is a shared httpx client, `ctx.cache` the TTLCache |
| `parse(raw) -> dict` | normalise to `{summary keys…, rows: [...]}` |
| `schema() -> dict` | describe the UI: `title`, `icon`, `category`, `summary_keys`, and a `table` or `sections` |

Add a source = drop one file + (if it needs keys) a config block. A tab appears
automatically; no route or HTML change.

### schema() shapes

```python
{"title": "...", "icon": "/icons/...", "category": "api|feed|status|probe|meta",
 "summary_keys": ["k1", "k2"],
 "table": {"rows_key": "rows", "columns": [
     {"key": "c", "label": "C", "badge": True},          # colour by value
     {"key": "name", "label": "Name", "link_key": "url"}, # cell links out
     {"key": "p", "label": "P", "icon_key": "icon"}]}}    # icon before text
```
Multi-table sources (e.g. Atera: tickets then alerts) use `sections: [{title, table}]`.

## Sources today

| id | category | upstream | creds |
|---|---|---|---|
| bgp | api | RIPEstat / RIPE DB (RPKI/IRR) | no |
| rootmon | probe | DNS roots A–M (UDP SOA + TCP) | no |
| news_feed | feed | OPML + curated RSS | no |
| acn_misp | feed | CSIRT-Italia MISP + ACN RSS | no |
| cloud_status | status | AWS/Azure RSS, GCP incidents, Statuspage (CF/Scaleway/DO/Linode); Office 365 separated | no |
| shodan | api | Shodan SDK | key + targets |
| netlas | api | Netlas API | key + targets |
| atera | api | Atera RMM | key |
| assets | meta | merges shodan+netlas per asset + DNS resolve | — |
| correlation | meta | cross-source IOC overlap | — |
| opencti | meta | STIX bundle over collected IOCs | — |

## core.py primitives

- `TTLCache` — in-process cache with stale-while-revalidate.
- `CircuitBreaker` — opens after N consecutive failures, half-opens after a reset window.
- `RefreshGate` — per-source cooldown + lock for manual `/api/refresh`.
- `safe_gather` — gather that isolates a failing task instead of sinking the batch.
- `Ctx` — shared httpx client + cache handed to every `fetch()`.

## HTTP API

| route | auth | purpose |
|---|---|---|
| `GET /` | open | the dashboard |
| `GET /api/sources` | open | registry + each `schema()` |
| `GET /api/health` | open | per-source ok/age/error |
| `GET /api/status` | open | config + runtime diagnostics (Status/About tab) |
| `GET /api/data/{id}` | open | latest cached, parsed payload |
| `POST /api/refresh/{id}` | **X-API-Key** | force a refresh (cooldown + lock) |

## Persistence

`cti/store.py` writes `state/cache/{id}.json` (atomic) and appends
`state/events.jsonl` (refresh ok/fail audit). No database; survives restarts.

## Deliberately NOT here (yet)

Redis, Celery, Prometheus, Docker, SQL, per-source microservices. Add only when
a single host genuinely no longer suffices.
