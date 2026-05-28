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


_ENRICH = ["risk_level", "risk_score", "open_ports", "vuln_count", "country", "org"]


async def fetch(cfg, ctx) -> dict:
    from .. import targets as tgt
    from .. import store as _store
    # seed every configured target so they always appear even before intel arrives
    assets: dict[str, dict] = {
        a: {"asset": a, "feeds": {}} for a in tgt.all_targets()
    }
    for feed, asset_key in _FEEDS.items():
        data = ctx.cache.get(feed, stale_ok=True) or {}
        for row in data.get("rows", []):
            asset = str(row.get(asset_key, "")).strip()
            if not asset:
                continue
            entry = assets.setdefault(asset, {"asset": asset, "feeds": {}})
            entry["feeds"][feed] = {k: row.get(k) for k in _ENRICH}
    names = list(assets)
    dns = await asyncio.gather(*[_resolve(a) for a in names])
    for a, d in zip(names, dns):
        assets[a]["dns"] = d
    # track first time each asset was seen under monitoring
    seen = _store.load_first_seen()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated = False
    for a in names:
        if a not in seen:
            seen[a] = now_iso
            updated = True
    if updated:
        _store.save_first_seen(seen)
    for a in names:
        assets[a]["first_seen"] = seen.get(a)
    return {"assets": list(assets.values()),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _best_feed(feeds: dict) -> tuple[str, dict]:
    """Return (feed_name, feed_data) for the feed with the most ports data."""
    def _has(v): return v not in (None, "-", 0)
    def _pn(v): return v if isinstance(v, int) else 0
    scored = [(f, d, _pn(d.get("open_ports"))) for f, d in feeds.items()]
    scored.sort(key=lambda x: -x[2])
    # prefer a feed that actually has data
    for f, d, ports in scored:
        if _has(ports) or _has(d.get("vuln_count")):
            return f, d
    # fallback: first feed with any risk_level
    for f, d, _ in scored:
        if d.get("risk_level"):
            return f, d
    return (scored[0][0], scored[0][1]) if scored else ("—", {})


def parse(raw: dict) -> dict:
    rows = []
    at_risk = 0
    for a in raw.get("assets", []):
        sh = a["feeds"].get("shodan", {})
        nl = a["feeds"].get("netlas", {})
        worst = _worst(sh.get("risk_level"), nl.get("risk_level"))
        if worst in ("high", "critical"):
            at_risk += 1
        try:
            import ipaddress as _ip
            _ip.ip_address(a["asset"])
            asset_type = "ip"
        except ValueError:
            asset_type = "domain"

        def _iv(d, k):
            v = d.get(k)
            return v if isinstance(v, int) else "—"

        rows.append({
            "asset": a["asset"],
            "type": asset_type,
            "dns": a.get("dns", "—"),
            "country": sh.get("country") or nl.get("country") or "—",
            "org": sh.get("org") or nl.get("org") or "—",
            "max_risk": worst or "—",
            "shodan_risk": sh.get("risk_level") or "—",
            "shodan_score": sh.get("risk_score"),
            "shodan_ports": _iv(sh, "open_ports"),
            "shodan_vulns": _iv(sh, "vuln_count"),
            "netlas_risk": nl.get("risk_level") or "—",
            "netlas_score": nl.get("risk_score"),
            "netlas_ports": _iv(nl, "open_ports"),
            "netlas_vulns": _iv(nl, "vuln_count"),
            "seen_in": ", ".join(sorted(a["feeds"].keys())),
            "first_seen": a.get("first_seen"),
        })
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    rows.sort(key=lambda r: -rank.get(r["max_risk"], 0))
    return {"assets_total": len(rows), "at_risk": at_risk, "rows": rows}


def schema() -> dict:
    return {
        "title": "Assets",
        "icon": ICON,
        "category": "meta",
        "widget": "intel",
        "summary_keys": ["assets_total", "at_risk"],
    }
