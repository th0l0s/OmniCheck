"""
correlation — cross-source IOC overlap (a meta-source, no upstream fetch).

Reads the already-collected, cached output of the other sources and surfaces
any IOC value that appears in more than one of them. The high-value case: an
IP/domain that is BOTH a threat IOC (ACN/MISP feed) AND one of your monitored
assets (Shodan / Netlas watchlist) — i.e. your own asset showing up in a threat
feed. Replaces the old aggregator's correlator, but driven by the live cache.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

log = logging.getLogger("cti.correlation")

ID = "correlation"
NAME = "IOC Correlation"
INTERVAL = 600

_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _kind(value: str) -> str:
    if _IP_RE.match(value):
        return "ip"
    if ":" in value and value.count(":") >= 2:
        return "ipv6"
    if re.fullmatch(r"[a-fA-F0-9]{32,64}", value):
        return "hash"
    if "." in value:
        return "domain"
    return "other"


def _norm(value: str) -> str:
    # ip-dst|port and filename|hash style values: keep the left side.
    return (value or "").split("|", 1)[0].strip().lower()


async def fetch(cfg, ctx) -> dict:
    """Pull IOC-bearing fields from the live cache of the other sources."""
    # value -> {sources: set, type: str}
    seen: dict[str, dict] = {}

    def add(value: str, source: str, type_hint: str = ""):
        v = _norm(value)
        if not v or len(v) < 4:
            return
        entry = seen.setdefault(v, {"sources": set(), "type": type_hint or _kind(v)})
        entry["sources"].add(source)

    acn = ctx.cache.get("acn_misp", stale_ok=True) or {}
    for ioc in acn.get("iocs", []):
        t = ioc.get("type", "")
        hint = "ip" if t.startswith("ip-") else ("domain" if t in ("domain", "hostname")
                else ("hash" if t in ("md5", "sha1", "sha256") else ""))
        add(ioc.get("value", ""), "ACN/MISP", hint)

    shodan = ctx.cache.get("shodan", stale_ok=True) or {}
    for row in shodan.get("rows", []):
        add(row.get("ip", ""), "Shodan", "ip")

    netlas = ctx.cache.get("netlas", stale_ok=True) or {}
    for row in netlas.get("rows", []):
        add(row.get("target", ""), "Netlas")

    correlated = [
        {"ioc": v, "type": e["type"], "sources": sorted(e["sources"]), "hits": len(e["sources"])}
        for v, e in seen.items() if len(e["sources"]) >= 2
    ]
    correlated.sort(key=lambda x: (-x["hits"], x["type"]))
    return {"correlated": correlated, "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    corr = raw.get("correlated", [])
    rows = [{"ioc": c["ioc"], "type": c["type"], "sources": ", ".join(c["sources"]),
             "hits": c["hits"]} for c in corr]
    return {"correlated_iocs": len(rows),
            "max_overlap": max((c["hits"] for c in corr), default=0),
            "rows": rows}


def schema() -> dict:
    return {
        "title": "IOC Correlation",
        "description": "Cross-source IOC overlap: indicators appearing in ACN/MISP, Shodan, and Netlas",
        "icon": "/icons/security/icons8-fingerprint-50.png",
        "category": "meta",
        "summary_keys": ["correlated_iocs", "max_overlap"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "ioc",     "label": "IOC",      "mono": True},
                {"key": "type",    "label": "Type",     "badge": True},
                {"key": "sources", "label": "Seen in"},
                {"key": "hits",    "label": "Sources",  "numeric": True},
            ],
        },
    }
