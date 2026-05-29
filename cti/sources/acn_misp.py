"""
acn_misp — CSIRT-Italia MISP feed (manifest + per-event IOCs) and ACN RSS.

No credentials. Pulls the public MISP feed manifest, loads the most recent
events to extract IOCs, and merges the ACN portal RSS. Threat level mapping is
the MISP standard (1=High … 4=Undefined).
"""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger("cti.acn")

ID = "acn_misp"
NAME = "ACN / CSIRT-IT"
INTERVAL = 900  # 15 min

FEED_BASE = "https://www.csirt.gov.it/feed-misp"
RSS_URL = "https://www.acn.gov.it/portale/feedrss/-/journal/rss/20119/723192"
EVENTS_LIMIT = 8

THREAT_LEVEL = {1: "high", 2: "medium", 3: "low", 4: "undefined"}

_LEVEL_ICONS = {
    "high":      "/icons/security/icons8-fire-50.png",
    "medium":    "/icons/misc/icons8-info-50.png",
    "low":       "/icons/security/icons8-shield-50.png",
    "undefined": "/icons/misc/icons8-info-50.png",
}
IOC_TYPES = {
    "ip-dst", "ip-src", "ip-dst|port", "domain", "hostname", "url",
    "md5", "sha1", "sha256", "filename", "email-src", "email-dst", "regkey", "mutex",
}


def _ts_iso(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def _strip_html(s):
    return re.sub(r"<[^>]+>", " ", s or "").strip()


def _parse_manifest(data, limit=0):
    items = []
    for uuid, ev in (data or {}).items():
        tl = int(ev.get("threat_level_id", 4))
        items.append({
            "uuid": uuid, "info": ev.get("info", ""), "date": ev.get("date", ""),
            "timestamp": int(ev.get("timestamp", 0)),
            "published_at": _ts_iso(ev.get("timestamp", 0)),
            "threat_level": THREAT_LEVEL.get(tl, "undefined"),
            "org": ev.get("Orgc", {}).get("name", ""),
        })
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items[:limit] if limit else items


def _parse_event(data):
    ev = data.get("Event", data)
    iocs = []
    blocks = list(ev.get("Attribute", []))
    for obj in ev.get("Object", []):
        blocks.extend(obj.get("Attribute", []))
    for attr in blocks:
        t = attr.get("type", "")
        if t in IOC_TYPES:
            iocs.append({"type": t, "value": attr.get("value", ""),
                         "category": attr.get("category", "")})
    return {"uuid": ev.get("uuid", ""), "info": ev.get("info", ""),
            "ioc_count": len(iocs), "iocs": iocs}


def _parse_rss(xml_bytes):
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    for item in root.findall(".//item"):
        pub = (item.findtext("pubDate") or "").strip()
        try:
            pub = parsedate_to_datetime(pub).isoformat() if pub else ""
        except Exception:
            pass
        items.append({"title": (item.findtext("title") or "").strip(),
                      "link": (item.findtext("link") or "").strip(),
                      "summary": _strip_html(item.findtext("description") or ""),
                      "published": pub})
    return items


async def fetch(cfg, ctx) -> dict:
    base = cfg.get("feed_url", FEED_BASE)
    rss_url = cfg.get("rss_url", RSS_URL)

    async def manifest():
        r = await ctx.client.get(f"{base}/manifest.json")
        r.raise_for_status()
        return r.json()

    async def rss():
        try:
            r = await ctx.client.get(rss_url)
            r.raise_for_status()
            return _parse_rss(r.content)
        except Exception as exc:
            log.warning("ACN RSS fetch failed: %s", exc)
            return []

    raw_manifest, rss_items = await asyncio.gather(manifest(), rss())
    summaries = _parse_manifest(raw_manifest, limit=EVENTS_LIMIT)

    async def load(s):
        try:
            r = await ctx.client.get(f"{base}/{s['uuid']}.json")
            r.raise_for_status()
            return _parse_event(r.json())
        except Exception as exc:
            log.warning("ACN event %s failed: %s", s["uuid"], exc)
            return {"uuid": s["uuid"], "info": s["info"], "ioc_count": 0, "iocs": []}

    events = await asyncio.gather(*[load(s) for s in summaries])
    return {"manifest": _parse_manifest(raw_manifest), "events": list(events), "rss": rss_items}


def parse(raw: dict) -> dict:
    manifest = raw.get("manifest", [])
    events = raw.get("events", [])
    by_level = {}
    for ev in manifest:
        by_level[ev["threat_level"]] = by_level.get(ev["threat_level"], 0) + 1
    ev_by_uuid = {e["uuid"]: e for e in events}
    rows = []
    for m in manifest[:EVENTS_LIMIT]:
        rows.append({"info": m["info"], "threat_level": m["threat_level"],
                     "level_icon": _LEVEL_ICONS.get(m["threat_level"], _LEVEL_ICONS["undefined"]),
                     "org": m["org"], "date": m["date"],
                     "iocs": ev_by_uuid.get(m["uuid"], {}).get("ioc_count", 0)})
    total_iocs = sum(e["ioc_count"] for e in events)
    flat_iocs = [ioc for e in events for ioc in e.get("iocs", [])]
    return {
        "misp_total": len(manifest),
        "ioc_total": total_iocs,
        "rss_total": len(raw.get("rss", [])),
        "by_level": by_level,
        "rows": rows,
        "news": raw.get("rss", [])[:20],
        "iocs": flat_iocs,
    }


def schema() -> dict:
    return {
        "title": "ACN / CSIRT-IT",
        "description": "Italian CSIRT MISP threat intelligence events and ACN portal RSS advisories",
        "icon": "/icons/security/icons8-cyber-security-50.png",
        "category": "feed",
        "summary_keys": ["misp_total", "ioc_total", "rss_total"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "info",         "label": "Event"},
                {"key": "threat_level", "label": "Level",  "badge": True, "icon_key": "level_icon"},
                {"key": "org",          "label": "Org"},
                {"key": "date",         "label": "Date",   "mono": True},
                {"key": "iocs",         "label": "IOCs",   "numeric": True},
            ],
        },
    }
