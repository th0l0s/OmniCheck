"""
bgp — Italian backbone BGP / RPKI / IRR sentinel (public RIPEstat + RIPE DB).

No credentials. Per target ASN: resolve announced prefixes live, then for each
prefix check RPKI validation, global visibility and the IRR route object, and
score severity under the policy in config. RPKI is cryptographic truth and
dominates; IRR is administrative; not-found != hijack.

Targets and policy live in config.yaml under sources.bgp; sensible Italian-ISP
defaults are baked in so an empty config still produces a useful scan.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("cti.bgp")

RIPESTAT = "https://stat.ripe.net/data"
RIPE_DB = "https://rest.db.ripe.net"

ID = "bgp"
NAME = "BGP Watch IT"
INTERVAL = 1800  # 30 min

_DEFAULT_TARGETS = [
    {"name": "TIM", "group": "italian-isp", "role": "isp", "asns": [3269, 16232, 20746]},
    {"name": "Wind Tre", "group": "italian-isp", "role": "isp", "asns": [1267, 24608]},
    {"name": "Fastweb", "group": "italian-isp", "role": "isp", "asns": [12874]},
    {"name": "Vodafone Italia", "group": "italian-isp", "role": "isp", "asns": [30722, 12663]},
    {"name": "Tiscali", "group": "italian-isp", "role": "isp", "asns": [8612]},
    {"name": "EOLO", "group": "italian-isp", "role": "isp", "asns": [35612]},
    {"name": "Open Fiber", "group": "italian-isp", "role": "isp", "asns": [210218]},
    {"name": "Aruba", "group": "italian-datacenter", "role": "datacenter", "asns": [31034]},
    {"name": "Retelit", "group": "italian-datacenter", "role": "datacenter", "asns": [3302]},
]

_POLICY = {
    "severity": {
        "rpki_invalid": "critical", "irr_unauthorized": "critical",
        "no_route_object": "warning", "rpki_not_found": "warning",
        "not_globally_visible": "warning",
    },
    "risk_score": {
        "rpki_invalid": 45, "irr_unauthorized": 35, "no_route_object": 15,
        "rpki_not_found": 10, "not_globally_visible": 15,
    },
    "critical_score": 70, "warning_score": 30,
}

MAX_PREFIXES = 25
_sem = asyncio.Semaphore(8)


async def _get(client, url, params):
    async with _sem:
        for attempt in (1, 2):
            try:
                r = await client.get(url, params=params, timeout=12.0)
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                if attempt == 2:
                    log.warning("GET %s failed: %s", url, exc)
                    return None
                await asyncio.sleep(0.4)
    return None


async def _announced(client, asn):
    d = await _get(client, f"{RIPESTAT}/announced-prefixes/data.json", {"resource": f"AS{asn}"})
    if not d:
        return []
    return [p["prefix"] for p in d.get("data", {}).get("prefixes", []) if p.get("prefix")]


async def _rpki(client, asn, prefix):
    d = await _get(client, f"{RIPESTAT}/rpki-validation/data.json",
                   {"resource": f"AS{asn}", "prefix": prefix})
    if not d:
        return {"status": "error"}
    raw = str(d.get("data", {}).get("status", "")).lower()
    status = {"valid": "valid", "invalid": "invalid", "invalid_asn": "invalid",
              "invalid_length": "invalid", "unknown": "not-found",
              "not-found": "not-found"}.get(raw, "not-found")
    return {"status": status}


async def _propagation(client, asn, prefix):
    d = await _get(client, f"{RIPESTAT}/routing-status/data.json", {"resource": prefix})
    if not d:
        return {"visible": False, "peers_seen": None, "total_peers": None}
    vis = d.get("data", {}).get("visibility", {})
    bucket = vis.get("v6" if ":" in prefix else "v4", {}) or {}
    seen = bucket.get("ris_peers_seeing")
    return {"visible": bool(seen and seen > 0), "peers_seen": seen,
            "total_peers": bucket.get("total_ris_peers")}


async def _irr(client, asn, prefix):
    kind = "route6" if ":" in prefix else "route"
    d = await _get(client, f"{RIPE_DB}/search.json",
                   {"query-string": prefix, "type-filter": kind, "flags": "no-referenced"})
    if d is None:
        return {"status": "error"}
    objs = (d.get("objects", {}) or {}).get("object", []) or []
    origins = []
    for obj in objs:
        attrs = {a["name"]: a["value"] for a in obj.get("attributes", {}).get("attribute", [])
                 if "name" in a and "value" in a}
        try:
            origins.append(int(str(attrs.get("origin", "")).upper().replace("AS", "")))
        except ValueError:
            pass
    if not objs:
        return {"status": "not-found"}
    return {"status": "authorized" if asn in origins else "unauthorized"}


def _score(rpki, irr, prop):
    if rpki["status"] == "error" or irr["status"] == "error":
        return {"severity": "source_error", "risk_score": 0, "reasons": ["source_error"]}
    reasons, score = [], 0

    def add(key):
        nonlocal score
        reasons.append(key)
        score += _POLICY["risk_score"].get(key, 0)

    if rpki["status"] == "invalid":
        add("rpki_invalid")
    elif rpki["status"] == "not-found":
        add("rpki_not_found")
    if irr["status"] == "unauthorized":
        add("irr_unauthorized")
    elif irr["status"] == "not-found":
        add("no_route_object")
    if not prop["visible"]:
        add("not_globally_visible")

    score = min(score, 100)
    if "rpki_invalid" in reasons or "irr_unauthorized" in reasons or score >= _POLICY["critical_score"]:
        sev = "critical"
    elif score >= _POLICY["warning_score"]:
        sev = "warning"
    elif reasons:
        sev = "info"
    else:
        sev = "ok"
    return {"severity": sev, "risk_score": score, "reasons": reasons}


async def _assess_prefix(client, asn, prefix):
    rpki, prop, irr = await asyncio.gather(
        _rpki(client, asn, prefix), _propagation(client, asn, prefix), _irr(client, asn, prefix))
    s = _score(rpki, irr, prop)
    return {"prefix": prefix, "origin_asn": asn, "rpki": rpki["status"],
            "visible": prop["visible"], "irr": irr["status"], **s}


async def _assess_asn(client, target, asn):
    prefixes = await _announced(client, asn)
    if not prefixes:
        return {"name": target["name"], "asn": asn, "group": target.get("group"),
                "severity": "source_error", "risk_score": 0, "reasons": ["source_error"],
                "prefixes_total": 0, "prefixes_checked": 0, "assessments": []}
    checked = prefixes[:MAX_PREFIXES]
    results = await asyncio.gather(*[_assess_prefix(client, asn, p) for p in checked])
    rank = {"ok": 0, "info": 1, "source_error": 1, "warning": 2, "critical": 3}
    worst, sev = 0, "ok"
    risk = 0
    for r in results:
        risk = max(risk, r["risk_score"])
        if rank.get(r["severity"], 0) > worst:
            worst, sev = rank[r["severity"]], r["severity"]
    return {"name": target["name"], "asn": asn, "group": target.get("group"),
            "role": target.get("role"), "severity": sev, "risk_score": risk,
            "prefixes_total": len(prefixes), "prefixes_checked": len(checked),
            "assessments": results}


async def fetch(cfg, ctx) -> dict:
    targets = cfg.get("targets") or _DEFAULT_TARGETS
    jobs = []
    for t in targets:
        for asn in t.get("asns", []):
            jobs.append(_assess_asn(ctx.client, t, int(asn)))
    return {"targets": await asyncio.gather(*jobs)}


def parse(raw: dict) -> dict:
    targets = raw.get("targets", [])
    summary = {"ok": 0, "info": 0, "warning": 0, "critical": 0, "source_error": 0}
    critical, prefixes = [], 0
    for t in targets:
        summary[t["severity"]] = summary.get(t["severity"], 0) + 1
        prefixes += t.get("prefixes_checked", 0)
        for a in t.get("assessments", []):
            if a["severity"] == "critical":
                critical.append({"target": t["name"], "asn": t["asn"],
                                 "prefix": a["prefix"], "reasons": a["reasons"]})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "targets_checked": len(targets),
        "prefixes_checked": prefixes,
        "summary": summary,
        "critical": critical,
        "rows": [{"target": t["name"], "asn": f"AS{t['asn']}", "group": t.get("group", ""),
                  "severity": t["severity"], "risk_score": t["risk_score"],
                  "prefixes": t.get("prefixes_checked", 0)} for t in targets],
    }


def schema() -> dict:
    return {
        "title": "BGP Watch IT",
        "description": "RPKI, IRR and global visibility checks for Italian ISP ASNs via RIPEstat",
        "icon": "/icons/network/icons8-internet-50.png",
        "category": "api",
        "summary_keys": ["targets_checked", "prefixes_checked"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "target",     "label": "Operator"},
                {"key": "asn",        "label": "ASN",      "mono": True},
                {"key": "group",      "label": "Group"},
                {"key": "severity",   "label": "Severity", "badge": True},
                {"key": "risk_score", "label": "Risk",     "numeric": True},
                {"key": "prefixes",   "label": "Prefixes", "numeric": True},
            ],
        },
        "tools": [
            {"tool": "whois", "label": "whois ASN", "arg": "AS3269"},
            {"tool": "whois", "label": "whois prefix", "arg": "2.36.0.0/16"},
            {"tool": "dig", "label": "dig origin", "arg": "1.0.0.0.asn.routeviews.org", "extra": "TXT"},
        ],
        "layer": 0,
        "kind": "internet_health",
        "overview": True,
    }
