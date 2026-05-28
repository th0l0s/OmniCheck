# CTI Sentinel

One binary. One scheduler. One dashboard. A personal threat-intelligence
sentinel that collects from several sources via their APIs and presents them in
a single, professional dashboard.

This is the **Plan B consolidation** of the former 10 micro-services (see
`REPORT_ANTIREZ_REVIEW.md`): instead of a FastAPI app per source plus an
aggregator plus 6 systemd units plus 4 separate HTML dashboards, everything now
lives in one package, `cti/`.

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
│   └── atera.py      RMM alerts/tickets/offline servers (needs ATERA_API_KEY)
└── static/index.html  ONE dashboard; tabs are built from each source's schema()
```

**The source contract** — a file in `sources/` is a source if it exposes:

- `ID`, `NAME`, `INTERVAL` (seconds)
- `async fetch(cfg, ctx) -> raw` — pull from upstream (`ctx.client` is a shared httpx client)
- `parse(raw) -> dict` — normalise to the dashboard shape
- `schema() -> dict` — describe the UI tab (summary cards + table columns)
- optional `REQUIRES = [...]` — config keys that must be set or the source is skipped

Adding a source = drop one file in `sources/` + fill its config block. A tab
appears automatically. No new route, no new HTML.

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

- `GET /` — the dashboard
- `GET /api/sources` — registry + each source's `schema()` (drives the tabs)
- `GET /api/health` — per-source `{ok, last_fetch, age_s, error}`
- `GET /api/data/{id}` — latest cached, parsed payload for one source
- `POST /api/refresh/{id}` — force an immediate refresh

## Migration note

The previous 10 micro-services and their 6 systemd units have been removed; all
logic now lives in `cti/sources/`. A snapshot of the legacy code is kept as
`cti_legacy_backup.zip` (local) and `/opt/cti_legacy_backup.tar.gz` (remote) in
case anything needs to be recovered.
