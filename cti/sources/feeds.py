"""
feeds — unified intelligence feed panel (meta-source, no upstream fetch).

Reads the cached output of news_feed and acn_misp and merges them into a
single newest-first timeline. Every item carries type/category/source fields
that drive the multi-dimensional filter chips in the dashboard.

  type: news    — article from RSS feeds (news_feed)
  type: advisory — ACN portal RSS advisory
  type: misp     — CSIRT-IT MISP event
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("cti.feeds")

ID = "feeds"
NAME = "Intel Feeds"
INTERVAL = 300

_CAT_ICONS = {
    "authority_it":  "/icons/security/icons8-gdpr-50.png",
    "authority_eu":  "/icons/security/icons8-gdpr-50.png",
    "authority_us":  "/icons/security/icons8-shield-50.png",
    "threat_intel":  "/icons/security/icons8-fire-50.png",
    "vuln_db":       "/icons/security/icons8-virus-50.png",
    "media_en":      "/icons/network/icons8-rss-50.png",
    "media_it":      "/icons/network/icons8-rss-50.png",
    "general":       "/icons/misc/icons8-info-50.png",
}

_THREAT_ICON = {
    "high":    "/icons/security/icons8-fire-50.png",
    "medium":  "/icons/misc/icons8-info-50.png",
    "low":     "/icons/security/icons8-shield-50.png",
}


def _ts(s: str) -> str:
    """Normalise to YYYY-MM-DD HH:MM for display and sortable comparison."""
    if not s:
        return ""
    return str(s)[:16].replace("T", " ")


async def fetch(cfg, ctx) -> dict:
    items: list[dict] = []

    news = ctx.cache.get("news_feed", stale_ok=True) or {}
    for row in news.get("rows", []):
        items.append({
            "ts_sort": row.get("published", ""),
            "published": _ts(row.get("published", "")),
            "type": "news",
            "category": row.get("category", "general"),
            "category_icon": row.get("category_icon") or _CAT_ICONS.get(row.get("category", "general"), ""),
            "source": row.get("source", ""),
            "title": row.get("title", ""),
            "link": row.get("link", ""),
            "badge_icon": "",
            "extra": "",
        })

    acn = ctx.cache.get("acn_misp", stale_ok=True) or {}

    for item in acn.get("news", []):
        items.append({
            "ts_sort": item.get("published", ""),
            "published": _ts(item.get("published", "")),
            "type": "advisory",
            "category": "authority_it",
            "category_icon": _CAT_ICONS["authority_it"],
            "source": "ACN Portal",
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "badge_icon": "",
            "extra": "",
        })

    for row in acn.get("rows", []):
        level = row.get("threat_level", "undefined")
        items.append({
            "ts_sort": row.get("date", ""),
            "published": row.get("date", ""),
            "type": "misp",
            "category": "threat_intel",
            "category_icon": _THREAT_ICON.get(level, _CAT_ICONS["threat_intel"]),
            "source": f"CSIRT-IT / {row.get('org', '').strip()}" if row.get("org") else "CSIRT-IT",
            "title": row.get("info", ""),
            "link": "",
            "badge_icon": "",
            "extra": f"{row.get('iocs', 0)} IOCs" if row.get("iocs") else "",
            "threat_level": level,
        })

    items.sort(key=lambda x: x.get("ts_sort", ""), reverse=True)

    return {
        "items": items,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def parse(raw: dict) -> dict:
    items = raw.get("items", [])
    types = sorted({i["type"] for i in items})
    cats = sorted({i["category"] for i in items if i.get("category")})
    sources = sorted({i["source"] for i in items if i.get("source")})
    return {
        "total": len(items),
        "rows": items,
        "types": types,
        "categories": cats,
        "sources": sources,
    }


def schema() -> dict:
    return {
        "title": "Intel Feeds",
        "icon": "/icons/network/icons8-rss-50.png",
        "category": "feed",
        "widget": "feeds",
        "summary_keys": ["total"],
    }
