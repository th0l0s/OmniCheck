"""
_template.py — skeleton for a new CTI data source.

Copy to cti/sources/your_name.py (drop the leading underscore), fill in the
five symbols below, add a config block in config.yaml. The registry discovers
it automatically; a tab appears on the dashboard with no other change required.

This file is ignored by the registry because ID is not defined at module level.
"""
from __future__ import annotations

# ── required symbols ──────────────────────────────────────────────────────────

# ID       = "my_source"      # unique slug — valid Python identifier, lowercase
# NAME     = "My Source"      # human-readable title shown on the dashboard
# INTERVAL = 300              # default refresh cadence in seconds
# REQUIRES = ["my_source.api_key"]  # config keys that must be truthy; omit if none

# ── fetch ─────────────────────────────────────────────────────────────────────

# async def fetch(cfg, ctx) -> dict:
#     """Pull from upstream. Return a raw dict; raise freely on failure.
#
#     ctx.client  — shared httpx.AsyncClient (headers, timeouts already set)
#     ctx.cache   — TTLCache; read siblings: ctx.cache.get("other_id", stale_ok=True)
#     cfg         — full config dict; your block is at cfg["sources"]["my_source"]
#     """
#     src = cfg.get("sources", {}).get(ID, {})
#     api_key = src.get("api_key", "")
#     r = await ctx.client.get(
#         "https://api.example.com/v1/data",
#         headers={"Authorization": f"Bearer {api_key}"},
#     )
#     r.raise_for_status()
#     return r.json()

# ── parse ─────────────────────────────────────────────────────────────────────

# def parse(raw: dict) -> dict:
#     """Normalise raw output to dashboard shape. Never raise.
#
#     Return a flat dict with:
#       • scalar keys listed in schema()["summary_keys"]  (shown as KPI numbers)
#       • "rows": list of dicts, one per table row
#     """
#     rows = [{"name": item["name"], "status": item["status"]}
#             for item in raw.get("items", [])]
#     return {"total": len(rows), "rows": rows}

# ── schema ────────────────────────────────────────────────────────────────────

# def schema() -> dict:
#     """Describe the UI. The dashboard builds the tab and table from this dict."""
#     return {
#         "title": NAME,
#         "icon": "/icons/network/icons8-internet-50.png",  # path under /icons/
#         "category": "api",          # api | feed | status | probe | meta
#         "summary_keys": ["total"],  # scalar keys from parse() → big KPI numbers
#         "table": {
#             "rows_key": "rows",
#             "columns": [
#                 {"key": "name",   "label": "Name"},
#                 {"key": "status", "label": "Status", "badge": True},
#                 # {"key": "url",   "label": "Link",    "link_key": "url"},
#                 # {"key": "icon",  "label": "Service", "icon_key": "icon"},
#             ],
#         },
#         # Advanced: swap the generic table for a custom widget renderer.
#         # Built-in widgets: "intel" (assets), "providerbar" (cloud providers).
#         # Add your own in static/index.html panelHtml() and export "widget": "name".
#         # "widget": "providerbar",
#     }

# ── config.yaml block to add ──────────────────────────────────────────────────
#
# sources:
#   my_source:
#     enabled: true
#     interval: 300          # overrides INTERVAL
#     api_key: ${MY_SOURCE_API_KEY}
#     # add source-specific keys here
