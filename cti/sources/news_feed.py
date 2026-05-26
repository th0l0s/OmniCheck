"""
news_feed — CTI news timeline from OPML collections + curated feeds.yaml.

No credentials. Discovers feeds from OPML URLs (deduped), fetches them with
bounded concurrency, and merges into a newest-first timeline with macrocategory
inference. The scheduler runs this in the background, so the dashboard route
never blocks on 290 slow feeds (the incident that motivated Plan B).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import yaml

log = logging.getLogger("cti.news")

ID = "news_feed"
NAME = "News Feed"
INTERVAL = 1800  # 30 min

_DEFAULT_OPML = [
    "https://raw.githubusercontent.com/ransomfeed/cyber-news/refs/heads/main/feeds.opml",
    "https://raw.githubusercontent.com/cudeso/OPML-Security-Feeds/master/feedly.opml",
]
FEEDS_YAML = Path(__file__).resolve().parents[2] / "feeds.yaml"
MAX_CONCURRENT = 40
MAX_ITEMS_FEED = 10

_CAT_RULES = [
    (["acn.gov.it", "csirt", "agid.gov.it", "garanteprivacy.it"], "authority_it"),
    (["enisa.europa.eu", "cert.europa.eu"], "authority_eu"),
    (["cisa.gov", "nist.gov", "us-cert"], "authority_us"),
    (["urlhaus", "abuse.ch", "exploit-db", "greynoise", "ransomware", "leak"], "threat_intel"),
    (["nvd.nist", "cve."], "vuln_db"),
    (["bleepingcomputer", "securityweek", "therecord", "darkreading", "krebs"], "media_en"),
    (["cybersecurity360", "cybersecitalia", "ictsecuritymagazine"], "media_it"),
]


def _infer_category(url, title):
    hay = f"{url} {title}".lower()
    for patterns, cat in _CAT_RULES:
        if any(p in hay for p in patterns):
            return cat
    return "general"


def _parse_opml(xml_text):
    feeds = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return feeds
    for outline in root.iter("outline"):
        url = (outline.get("xmlUrl") or "").strip()
        if not url:
            continue
        title = (outline.get("title") or outline.get("text") or url).strip()
        feeds.append({"title": title, "url": url,
                      "html_url": outline.get("htmlUrl", ""),
                      "category": _infer_category(url, title)})
    return feeds


def _load_curated():
    if not FEEDS_YAML.exists():
        return []
    try:
        doc = yaml.safe_load(FEEDS_YAML.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out = []
    for f in doc.get("feeds", []):
        if f.get("enabled", True) and f.get("kind", "rss") == "rss" and f.get("url"):
            out.append({"title": f.get("name", f.get("id", "")), "url": f["url"],
                        "html_url": f["url"], "category": f.get("category", "general")})
    return out


def _clean(text, maxlen=300):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:maxlen] + "…") if len(text) > maxlen else text


def _parse_dt(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


async def _load_sources(client, opml_urls):
    seen, sources = set(), []

    async def one(url):
        try:
            r = await client.get(url)
            r.raise_for_status()
            return _parse_opml(r.text)
        except Exception as exc:
            log.warning("OPML fetch failed %s: %s", url, exc)
            return []

    for parsed in await asyncio.gather(*[one(u) for u in opml_urls]):
        for s in parsed:
            if s["url"] not in seen:
                seen.add(s["url"])
                sources.append(s)
    for c in _load_curated():
        if c["url"] not in seen:
            seen.add(c["url"])
            sources.append(c)
    return sources


async def fetch(cfg, ctx) -> dict:
    opml_urls = cfg.get("opml_urls") or _DEFAULT_OPML
    sources = await _load_sources(ctx.client, opml_urls)
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def feed(src):
        async with sem:
            try:
                r = await ctx.client.get(src["url"], timeout=10.0)
                r.raise_for_status()
                raw = r.text
            except Exception:
                return []
        items = []
        for entry in feedparser.parse(raw).entries[:MAX_ITEMS_FEED]:
            link = getattr(entry, "link", "") or ""
            title = _clean(getattr(entry, "title", "") or "Untitled", 200)
            items.append({
                "id": hashlib.sha1(f"{link}{title}".encode()).hexdigest()[:12],
                "title": title, "link": link,
                "summary": _clean(getattr(entry, "summary", "") or
                                  getattr(entry, "description", "") or ""),
                "published": _parse_dt(entry).isoformat(),
                "source": src["title"], "category": src["category"]})
        return items

    batches = await asyncio.gather(*[feed(s) for s in sources], return_exceptions=True)
    items = [i for b in batches if isinstance(b, list) for i in b]
    items.sort(key=lambda x: x["published"], reverse=True)
    return {"sources_loaded": len(sources), "items": items}


def parse(raw: dict) -> dict:
    items = raw.get("items", [])
    by_cat = {}
    for i in items:
        by_cat[i["category"]] = by_cat.get(i["category"], 0) + 1
    rows = [{"published": i["published"][:16].replace("T", " "), "category": i["category"],
             "source": i["source"], "title": i["title"], "link": i["link"]}
            for i in items[:60]]
    return {
        "sources_loaded": raw.get("sources_loaded", 0),
        "total_items": len(items),
        "by_category": by_cat,
        "rows": rows,
    }


def schema() -> dict:
    return {
        "title": "News Feed",
        "icon": "/icons/network/icons8-rss-50.png",
        "category": "feed",
        "summary_keys": ["sources_loaded", "total_items"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "published", "label": "When"},
                {"key": "category", "label": "Category", "badge": True},
                {"key": "source", "label": "Source"},
                {"key": "title", "label": "Title", "link_key": "link"},
            ],
        },
    }
