"""
assets — unified per-asset view across the intel feeds (meta-source).

Reads the cached, parsed output of the asset-centric feeds (currently Shodan
and Netlas) and merges them by asset value (IP or domain) into one list, so you
see every feed's verdict for a given asset on a single row. No upstream fetch.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from datetime import datetime, timezone

log = logging.getLogger("cti.assets")

ID = "assets"
NAME = "Assets"
INTERVAL = 300
ICON = "/icons/network/icons8-web-address-50.png"

_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "clean": 0, "error": 0, None: -1}

# feed id -> (rows_key, asset_key)
_FEEDS = {"shodan": "ip", "netlas": "target"}


def _worst(*levels):
    best, lv = -2, None
    for l in levels:
        r = _RANK.get(l, -1)
        if r > best:
            best, lv = r, l
    return lv


async def _resolve(asset: str) -> str:
    """DNS status for the asset: the IP itself for an IP, an A record for a
    domain, or NXDOMAIN/error. Bounded so it never hangs the refresh."""
    try:
        ipaddress.ip_address(asset)
        return "self (ip)"
    except ValueError:
        pass
    try:
        loop = asyncio.get_event_loop()
        infos = await asyncio.wait_for(
            loop.getaddrinfo(asset, None, family=socket.AF_INET), timeout=3.0)
        return infos[0][4][0] if infos else "no-record"
    except (asyncio.TimeoutError, socket.gaierror):
        return "NXDOMAIN"
    except Exception as exc:
        log.debug("dns resolve %s failed: %s", asset, exc)
        return "error"


async def fetch(cfg, ctx) -> dict:
    assets: dict[str, dict] = {}
    for feed, asset_key in _FEEDS.items():
        data = ctx.cache.get(feed, stale_ok=True) or {}
        for row in data.get("rows", []):
            asset = str(row.get(asset_key, "")).strip()
            if not asset:
                continue
            entry = assets.setdefault(asset, {"asset": asset, "feeds": {}})
            entry["feeds"][feed] = {
                "risk_level": row.get("risk_level"),
                "risk_score": row.get("risk_score"),
                "open_ports": row.get("open_ports"),
                "vuln_count": row.get("vuln_count"),
            }
    # resolve DNS for all assets concurrently (bounded per-lookup)
    names = list(assets)
    dns = await asyncio.gather(*[_resolve(a) for a in names])
    for a, d in zip(names, dns):
        assets[a]["dns"] = d
    return {"assets": list(assets.values()),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    rows = []
    at_risk = 0
    for a in raw.get("assets", []):
        sh = a["feeds"].get("shodan", {})
        nl = a["feeds"].get("netlas", {})
        worst = _worst(sh.get("risk_level"), nl.get("risk_level"))
        if worst in ("high", "critical"):
            at_risk += 1
        rows.append({
            "asset": a["asset"],
            "dns": a.get("dns", "—"),
            "max_risk": worst or "—",
            "shodan": sh.get("risk_level") or "—",
            "netlas": nl.get("risk_level") or "—",
            "ports": sh.get("open_ports") if sh.get("open_ports") not in (None, "-") else nl.get("open_ports", "—"),
            "seen_in": ", ".join(sorted(a["feeds"].keys())),
        })
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    rows.sort(key=lambda r: -rank.get(r["max_risk"], 0))
    return {"assets_total": len(rows), "at_risk": at_risk, "rows": rows}


def schema() -> dict:
    return {
        "title": "Assets",
        "icon": ICON,
        "category": "meta",
        "summary_keys": ["assets_total", "at_risk"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "asset", "label": "Asset (IP / domain)"},
                {"key": "dns", "label": "DNS"},
                {"key": "max_risk", "label": "Max Risk", "badge": True},
                {"key": "shodan", "label": "Shodan", "badge": True},
                {"key": "netlas", "label": "Netlas", "badge": True},
                {"key": "ports", "label": "Ports"},
                {"key": "seen_in", "label": "Feeds"},
            ],
        },
    }
