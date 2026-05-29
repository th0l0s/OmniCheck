"""
cloud_status — public operational status of European (and global) hyperscalers.

No credentials, no cloud SDKs: just GETs to the providers' public status pages.
Most use Atlassian Statuspage (`/api/v2/summary.json`); Google Cloud exposes a
custom `incidents.json`. The provider list lives in config.yaml — add or fix a
URL there, no code change (antirez "describe the data, don't encode it").
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import feedparser

log = logging.getLogger("cti.cloud")

ID = "cloud_status"
NAME = "Cloud Status"
INTERVAL = 300  # 5 min

# Default set — all credential-free public endpoints, verified live.
#   statuspage : Atlassian Statuspage  /api/v2/summary.json
#   gcp        : Google Cloud           incidents.json
#   rss        : AWS / Azure public status RSS feeds
# OVHcloud and Hetzner no longer expose a machine-readable status endpoint
# (HTML SPA only), so they are not defaulted; add them in config.yaml with a
# working url if one becomes available. Each provider also carries `page`, the
# human status page the dashboard links its indicator to.
_ICONS = {
    "aws": "/icons/cloud/icons8-amazon-aws-50.png",
    "azure": "/icons/cloud/icons8-azure-50.png",
    "office": "/icons/brand/icons8-office-365-50.png",
    "google": "/icons/cloud/icons8-google-cloud-50.png",
    "cloudflare": "/icons/cloud/icons8-cloudflare-50.png",
    "ovh": "/icons/cloud/icons8-ovh-50.png",
    "_default": "/icons/cloud/icons8-cloud-50.png",
}


def _icon_for(name: str) -> str:
    low = name.lower()
    for k, v in _ICONS.items():
        if k != "_default" and k in low:
            return v
    return _ICONS["_default"]


_DEFAULT_PROVIDERS = [
    {"name": "AWS", "type": "rss", "url": "https://status.aws.amazon.com/rss/all.rss",
     "page": "https://health.aws.amazon.com/health/status", "region": "Global"},
    {"name": "Microsoft Azure", "type": "rss",
     "url": "https://azurestatuscdn.azureedge.net/en-us/status/feed/",
     "page": "https://status.azure.com/en-us/status", "region": "Global"},
    # Office 365 / M365 service health has no credential-free public feed; live
    # health needs the M365 admin (Graph serviceHealth) API. Shown separately,
    # honestly marked, with a link to the public status page.
    {"name": "Office 365", "type": "info", "url": "",
     "page": "https://status.cloud.microsoft", "region": "Global",
     "note": "needs M365 admin (Graph) auth for live health"},
    {"name": "Google Cloud", "type": "gcp", "url": "https://status.cloud.google.com/incidents.json",
     "page": "https://status.cloud.google.com", "region": "Global"},
    {"name": "Scaleway", "type": "statuspage", "url": "https://status.scaleway.com",
     "page": "https://status.scaleway.com", "region": "EU/FR"},
    {"name": "Cloudflare", "type": "statuspage", "url": "https://www.cloudflarestatus.com",
     "page": "https://www.cloudflarestatus.com", "region": "Global"},
    {"name": "DigitalOcean", "type": "statuspage", "url": "https://status.digitalocean.com",
     "page": "https://status.digitalocean.com", "region": "Global"},
    {"name": "Linode/Akamai", "type": "statuspage", "url": "https://status.linode.com",
     "page": "https://status.linode.com", "region": "Global"},
]

# Statuspage indicator -> our status vocabulary
_INDICATOR = {"none": "ok", "minor": "warning", "major": "critical",
              "critical": "critical", "maintenance": "info"}


async def _statuspage(client, p):
    url = p["url"].rstrip("/") + "/api/v2/summary.json"
    r = await client.get(url, timeout=12.0)
    r.raise_for_status()
    d = r.json()
    ind = (d.get("status") or {}).get("indicator", "none")
    desc = (d.get("status") or {}).get("description", "")
    incidents = [i for i in d.get("incidents", []) if i.get("status") != "resolved"]
    affected = [c.get("name") for c in d.get("components", [])
                if c.get("status") not in ("operational", None)]
    return {"status": _INDICATOR.get(ind, "info"), "detail": desc,
            "incidents": len(incidents), "affected": affected[:5]}


async def _gcp(client, p):
    r = await client.get(p["url"], timeout=12.0)
    r.raise_for_status()
    incidents = r.json()
    ongoing = [i for i in incidents if not i.get("end")]
    if not ongoing:
        return {"status": "ok", "detail": "All services available", "incidents": 0, "affected": []}
    worst = "warning"
    affected = []
    for i in ongoing:
        sev = str(i.get("severity", "")).lower()
        if sev in ("high", "critical"):
            worst = "critical"
        affected.extend(pi.get("title", "") for pi in i.get("affected_products", [])[:3])
    return {"status": worst, "detail": f"{len(ongoing)} ongoing incident(s)",
            "incidents": len(ongoing), "affected": affected[:5]}


async def _rss(client, p):
    r = await client.get(p["url"], timeout=12.0)
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = []
    latest_title = ""
    for e in feed.entries[:30]:
        t = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        when = datetime(*t[:6], tzinfo=timezone.utc) if t else None
        title = getattr(e, "title", "") or ""
        if not latest_title:
            latest_title = title
        if when and when >= cutoff:
            low = title.lower()
            if not any(k in low for k in ("resolved", "operating normally", "informational")):
                recent.append(title)
    if recent:
        return {"status": "warning", "detail": recent[0][:90], "incidents": len(recent), "affected": []}
    return {"status": "ok", "detail": latest_title[:90] or "No recent incidents",
            "incidents": 0, "affected": []}


async def _one(client, p):
    try:
        kind = p.get("type")
        if kind == "info":
            return {**p, "status": "info", "detail": p.get("note", "status page only"),
                    "incidents": 0, "affected": [], "ok": True}
        if kind == "gcp":
            res = await _gcp(client, p)
        elif kind == "rss":
            res = await _rss(client, p)
        else:
            res = await _statuspage(client, p)
        return {**p, **res, "ok": True}
    except Exception as exc:
        log.warning("cloud status %s failed: %s", p.get("name"), exc)
        return {**p, "status": "error", "detail": str(exc)[:80], "incidents": 0,
                "affected": [], "ok": False}


async def fetch(cfg, ctx) -> dict:
    providers = cfg.get("providers") or _DEFAULT_PROVIDERS
    results = await asyncio.gather(*[_one(ctx.client, p) for p in providers])
    return {"providers": list(results),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    provs = raw.get("providers", [])
    rows = []
    operational = degraded = 0
    for p in provs:
        st = p.get("status")
        if st == "ok":
            operational += 1
        elif st in ("warning", "critical", "major"):
            degraded += 1
        detail = p.get("detail", "")
        if p.get("affected"):
            detail += " — " + ", ".join(p["affected"])
        rows.append({"provider": p.get("name", ""), "region": p.get("region", ""),
                     "status": st, "incidents": p.get("incidents", 0), "detail": detail[:120],
                     "page": p.get("page", p.get("url", "")), "icon": _icon_for(p.get("name", ""))})
    return {"providers_total": len(provs), "operational": operational,
            "degraded": degraded, "rows": rows}


def schema() -> dict:
    return {
        "title": "Cloud Status",
        "description": "Operational status of European cloud providers (AWS, Azure, GCP, Hetzner, OVH…)",
        "icon": "/icons/cloud/icons8-cloud-50.png",
        "category": "status",
        "widget": "providerbar",
        "summary_keys": ["providers_total", "operational", "degraded"],
        "layer": 0,
        "kind": "internet_health",
        "overview": True,
    }
