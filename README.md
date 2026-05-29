# OmniCheck Cockpit

*API-driven CTI and infrastructure sentinel*

One binary. One scheduler. One dark cockpit dashboard. A personal
threat-intelligence sentinel that collects from several sources via their APIs
and presents them in a single, professional SOC-style interface.

This is the **Plan B consolidation** of the former 10 micro-services — instead
of a FastAPI app per source plus an aggregator plus 6 systemd units plus 4
separate HTML dashboards, everything now lives in one package, `cti/`.

## Why

The project had drifted: 10 services duplicating cache/config/logging, three
cloud SDKs for a dormant feature, Redis and Prometheus on a single host, four
dashboards on four ports. A solo tool must fit in one head. Plan B brings it
back to the manifesto: simple, flat, minimal dependencies, non-blocking routes,
deploy = one command.

## How it works

```
cti/
├── __main__.py     python -m cti  → uvicorn
├── main.py         the one FastAPI app: generic routes + serves the dashboard
├── core.py         TTL cache, safe_gather, circuit breaker, HTTP context
├── config.py       loads config.yaml, expands ${ENV_VAR}
├── registry.py     discovers source modules, tracks per-source health
├── scheduler.py    one asyncio loop per source, refreshes on its own cadence
├── sources/        one file = one source (fetch / parse / schema)
│   ├── bgp.py        BGP/RPKI/IRR sentinel for Italian backbone (no creds)
│   ├── rootmon.py    DNS root server (A–M) liveness (no creds)
│   ├── news_feed.py  OPML + curated RSS timeline (no creds)
│   ├── acn_misp.py   CSIRT-Italia MISP feed + ACN RSS (no creds)
│   ├── opencti.py    STIX 2.1 bundle export over collected IOCs
│   ├── shodan.py     IP intel + risk scoring (needs SHODAN_API_KEY + targets)
│   ├── netlas.py     host exposure intel (needs NETLAS_API_KEY + targets)
│   ├── assets.py     per-asset cross-source risk view (meta-source)
│   └── atera.py      RMM alerts/tickets/offline servers (needs ATERA_API_KEY)
└── static/
    ├── index.html          app shell (~50 lines, no logic)
    ├── css/
    │   ├── app.css         design tokens, reset, layout shell
    │   ├── cockpit.css     panels, tables, KPIs, cloud bar, feed widgets
    │   └── badges.css      status dots, badges, threat badge, animations
    └── js/
        ├── state.js        shared state + constants (no side effects)
        ├── api.js          fetch layer (loadAll, fetchJSON)
        ├── components.js   pure HTML builders (esc, badge, panelHtml, …)
        ├── render.js       DOM mutation (renderSidebar, renderWorkspace, …)
        └── app.js          entry point (navigation, polling, event wiring)
```

**The source contract** — a file in `sources/` is a source if it exposes:

- `ID`, `NAME`, `INTERVAL` (seconds)
- `async fetch(cfg, ctx) -> raw` — pull from upstream (`ctx.client` is a shared httpx client)
- `parse(raw) -> dict` — normalise to the dashboard shape
- `schema() -> dict` — describe the UI tab (summary cards + table columns)
- optional `REQUIRES = [...]` — config keys that must be set or the source is skipped

Adding a source = drop one file in `sources/` + fill its config block. A tab
appears automatically. No new route, no new HTML.

## Frontend architecture

The dashboard is a **framework-free single-page app** — no React, no Vue, no
build step, no CDN. The browser loads native ES modules directly:

```
app.js (entry point, type="module")
  ├── state.js    — shared mutable object; all other modules read/write it
  ├── api.js      — fetch wrappers; populates state.sources / state.data
  ├── render.js   — all DOM writes go here; reads state, never fetches
  └── components.js — pure HTML-string builders (no DOM access)
```

`schema()` is the **UI contract**. The frontend reads `/api/sources` on boot,
then generates sidebar tabs, summary metric cards, and data tables entirely from
each source's `schema()` output. Column types (`badge`, `mono`, `numeric`) and
special widgets (`intel`, `providerbar`, `feeds`) are declared in the schema —
no frontend changes needed when a new source is added.

Polling interval and read-only mode are served by `/api/ui`. When
`CTI_API_KEY` is not set, the UI hides all mutation controls (add/remove
targets, force-refresh) without any frontend hard-coding.

## Configure

All credentials and cadences live in `config.yaml`. Secrets are referenced from
the environment with `${VAR}` — keep the real values in `/opt/cti/.env` (loaded
by systemd) or your shell, never in the file.

```yaml
sources:
  shodan:
    enabled: true
    api_key: ${SHODAN_API_KEY}
    targets: ["8.8.8.8"]
```

A source whose `REQUIRES` keys are empty is skipped and shown as `off` in the
dashboard — the app still runs.

## Run

```bash
python -m cti                 # reads config.yaml, serves on :8000
```

Open `http://localhost:8000`.

## Deploy (Debian + systemd, single host)

```bash
cp cti.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cti
# updates thereafter:
git pull && systemctl restart cti
```

No Docker, no Redis, no Prometheus. Metrics are `/api/health` (JSON). If you
ever need Prometheus, add a 30-line exporter then.

## API

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/` | — | Dashboard (StaticFiles) |
| GET | `/api/ui` | — | App name, poll interval, readonly flag |
| GET | `/api/sources` | — | Registry + `schema()` for all sources (drives tabs) |
| GET | `/api/health` | — | Per-source `{ok, last_fetch, age_s, error}` |
| GET | `/api/data/{id}` | — | Latest cached, parsed payload for one source |
| GET | `/api/status` | — | Runtime diagnostics (version, config issues, errors) |
| GET | `/api/targets` | — | Current watchlist |
| POST | `/api/targets` | X-API-Key | Add/remove monitored targets |
| POST | `/api/refresh/{id}` | X-API-Key | Force an immediate source refresh |

Mutating endpoints require `X-API-Key: <value>` matching the `CTI_API_KEY`
environment variable. If the variable is unset the server is read-only and all
`POST` endpoints return `503`.

## Security

- All API strings are passed through `esc()` before `innerHTML` insertion — no
  raw API data ever reaches the DOM unescaped.
- Inline `onclick` attribute values use `jsq()` — a two-stage escaper (JS
  string literal, then HTML attribute encoding) to prevent injection through
  source names or target addresses.
- The API key is never stored in the DOM. Read-only mode is declared by the
  server (`/api/ui → readonly: true`); the frontend reacts by hiding controls.
- The raw JSON debug block (collapsed by default) is rendered via
  `esc(JSON.stringify(...))`, never injected raw.

## Further reading

`docs/UI_COCKPIT.md` — full frontend design reference: schema() contract,
column flags, widget types, severity color system, and extension guide.

## Migration note

The previous 10 micro-services and their 6 systemd units have been removed; all
logic now lives in `cti/sources/`. A snapshot of the legacy code is kept as
`cti_legacy_backup.zip` (local) and `/opt/cti_legacy_backup.tar.gz` (remote) in
case anything needs to be recovered.
