# OmniCheck Cockpit — UI Design System

## Architecture

The frontend is a self-contained, framework-free single-page app served by FastAPI's `StaticFiles` mount. No build step, no CDN, no transpiler.

```
cti/static/
  index.html          — minimal shell (50 lines)
  css/
    app.css           — design tokens, reset, layout shell
    cockpit.css       — content widgets (panels, tables, KPIs, filters)
    badges.css        — status dots, badges, threat badge, keyframes
  js/
    state.js          — shared state object + constants (no side effects)
    api.js            — fetch layer (loadAll, fetchJSON)
    components.js     — pure HTML builders (esc, badge, panelHtml, …)
    render.js         — DOM mutation (renderSidebar, renderWorkspace, …)
    app.js            — entry point (navigation, polling, event wiring)
```

JS modules use native ES module `import`/`export` — no bundler needed.
`app.js` is loaded with `<script type="module">` and exposes navigation
functions to inline `onclick` handlers via explicit `window.xxx = xxx`
assignments.

## Data contract: `schema()`

Every source in `cti/sources/` exposes a `schema()` function. The frontend
reads it from `GET /api/sources` and generates tabs and panels automatically.

### Minimal schema

```python
def schema() -> dict:
    return {
        "title": "My Source",          # required
        "category": "api",             # api | feed | status | probe | meta
    }
```

### Full schema with table

```python
def schema() -> dict:
    return {
        "title": "My Source",
        "description": "One sentence explaining what it monitors.",
        "icon": "/icons/network/icons8-dns-50.png",
        "category": "probe",
        "summary_keys": ["total", "ok", "fail"],   # metric cards
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "host",    "label": "Host",    "mono": True},
                {"key": "status",  "label": "Status",  "badge": True},
                {"key": "latency", "label": "ms",      "numeric": True},
            ],
        },
    }
```

### Column flags

| Flag       | Effect                                             |
|------------|----------------------------------------------------|
| `badge`    | Renders value as a color-coded badge               |
| `mono`     | Monospace font (IPs, ASNs, hashes, timestamps)     |
| `numeric`  | Dimmed right-aligned style for counts/scores       |
| `icon_key` | Reads an icon path from another field in the row   |
| `link_key` | Makes cell an `<a>` using another field as the URL |

### Widget schemas (no table required)

| `widget`       | Source   | Description                              |
|----------------|----------|------------------------------------------|
| `intel`        | assets   | Asset cross-source risk table            |
| `providerbar`  | cloud_status | Provider status list               |
| `feeds`        | feeds    | Feed item list with type/category filter |

### Sections (multi-table layout)

```python
"sections": [
    {"title": "Open Tickets", "table": { "rows_key": "ticket_rows", "columns": [...] }},
    {"title": "Recent Alerts", "table": { "rows_key": "alert_rows",  "columns": [...] }},
]
```

### Domain filter

Add `"domain_filter": true` alongside a `filter_key` in `table.columns` to
display filter chips above the table (one chip per unique value of `filter_key`).

## API endpoints used by the UI

| Method | Path                  | Auth         | Purpose                         |
|--------|-----------------------|--------------|---------------------------------|
| GET    | `/api/ui`             | none         | App name, poll interval, readonly |
| GET    | `/api/sources`        | none         | Registry + schema() for all sources |
| GET    | `/api/health`         | none         | Per-source liveness             |
| GET    | `/api/data/{id}`      | none         | Latest cached payload           |
| GET    | `/api/status`         | none         | Runtime diagnostics             |
| GET    | `/api/targets`        | none         | Current watchlist               |
| POST   | `/api/targets`        | X-API-Key    | Add/remove targets              |
| POST   | `/api/refresh/{id}`   | X-API-Key    | Force immediate refresh         |

## Severity color system

| Level           | Color   | CSS class    | Use                          |
|-----------------|---------|--------------|------------------------------|
| ok / clean      | Green   | `.st-ok`     | All checks pass              |
| info            | Blue    | `.badge.b-info` | Informational, no action  |
| warning         | Amber   | `.st-warn`   | Degraded, needs attention    |
| critical / high | Magenta | `.st-err`    | Immediate action required    |
| source_error    | Magenta | `.panel.s-err` | Source failing to fetch    |
| off / disabled  | Gray    | `.st-off`    | Source not configured        |

## Security rules

1. **All API strings are escaped** through `esc()` before insertion into `innerHTML`.
2. **Inline `onclick` values** go through `jsq()` — a two-stage escaper that
   sanitizes the string as a JS literal, then HTML-encodes the result.
3. **API key never in the DOM** — `readonly` mode is indicated by `/api/ui`
   returning `"readonly": true`; the UI hides mutation controls.
4. **Raw JSON debug block** is collapsed by default and rendered via `esc(JSON.stringify(...))`,
   never injected raw.

## Adding a new source

1. Create `cti/sources/mysource.py` with `ID`, `NAME`, `INTERVAL`, `fetch()`, `parse()`, `schema()`.
2. Add config block in `config.yaml` under `sources.mysource`.
3. Restart — the sidebar tab and overview panel appear automatically.

No frontend changes needed.

## Extending the UI

- **New KPI in overview**: add a tile to the `tiles` array in `kpiStrip()` (`components.js`).
- **New badge color**: add `.badge.b-myvalue` to `badges.css`.
- **New column type**: add a flag check in `tableHtml()` (`components.js`).
- **New widget type**: add a branch in `panelHtml()` and a renderer function (`components.js`).
