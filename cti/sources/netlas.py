"""
netlas — host/domain exposure intel + risk scoring for the configured targets.

Requires sources.netlas.api_key and a non-empty targets list. Queries the
Netlas responses API per target, normalises services/vulns, and scores risk on
the same CVE thresholds as the Shodan source plus sensitive-port exposure.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("cti.netlas")

ID = "netlas"
NAME = "Netlas Intel"
INTERVAL = 86400
REQUIRES = ["api_key"]

NETLAS_BASE = "https://app.netlas.io/api"
SENSITIVE_PORTS = {21, 22, 23, 25, 445, 1433, 1521, 3306, 3389, 5432, 5900,
                   6379, 9200, 8080, 8443, 27017}


def _severity(score):
    return ("critical" if score >= 9.0 else "high" if score >= 7.0
            else "medium" if score >= 4.0 else "low" if score > 0 else "unknown")


def _score(services, vuln_sev):
    score, factors = 0, []
    for sev, pts_each, cap in [("critical", 20, 40), ("high", 10, 20), ("medium", 5, 10)]:
        n = sum(1 for v in vuln_sev if v == sev)
        pts = min(n * pts_each, cap)
        if pts:
            score += pts
            factors.append(f"{n} {sev} CVE(s) (+{pts})")
    sensitive = [s for s in services if s in SENSITIVE_PORTS]
    if sensitive:
        pts = min(len(sensitive) * 12, 36)
        score += pts
        factors.append(f"sensitive ports {sensitive} (+{pts})")
    if len(services) >= 10:
        score += min((len(services) // 10) * 5, 15)
    score = min(score, 100)
    level = ("critical" if score >= 76 else "high" if score >= 51
             else "medium" if score >= 21 else "low" if score >= 1 else "clean")
    return score, level, factors


def _query_for(target: str) -> str:
    """Build Netlas query string: ip: for addresses, host: for domains."""
    import ipaddress
    try:
        ipaddress.ip_address(target)
        return f"ip:{target}"
    except ValueError:
        return f"host:{target}"


async def _fetch_responses(client, target, api_key):
    try:
        r = await client.get(f"{NETLAS_BASE}/responses/",
                             params={"q": _query_for(target), "source_type": "include", "start": 0},
                             headers={"X-API-Key": api_key}, timeout=20.0)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as exc:
        log.warning("netlas responses %s failed: %s", target, exc)
        return None


def _normalize(target, items):
    if items is None:
        return {"target": target, "risk_level": "error", "risk_score": None,
                "open_ports": "-", "vuln_count": "-", "error": "fetch failed"}
    ports, vuln_sev = set(), []
    seen_cve = set()
    for it in items:
        d = it.get("data", {})
        port = d.get("port")
        if port:
            try:
                ports.add(int(port))
            except (TypeError, ValueError):
                pass
        for entry in (d.get("cve") or []):
            if isinstance(entry, dict):
                cid = entry.get("name") or entry.get("id")
                cvss = entry.get("cvss3") or entry.get("cvss") or entry.get("score") or 0
            else:
                cid, cvss = entry, 0
            if cid and cid not in seen_cve:
                seen_cve.add(cid)
                vuln_sev.append(_severity(float(cvss or 0)))
    score, level, _ = _score(list(ports), vuln_sev)
    return {"target": target, "risk_level": level, "risk_score": score,
            "open_ports": len(ports), "vuln_count": len(vuln_sev)}


async def fetch(cfg, ctx) -> dict:
    from .. import targets as tgt
    api_key = cfg["api_key"]
    # assets.yaml is canonical; config.yaml targets is a fallback
    all_tgts = tgt.all_targets() or cfg.get("targets", [])
    items = await asyncio.gather(*[_fetch_responses(ctx.client, t, api_key) for t in all_tgts])
    targets = all_tgts
    return {"results": list(zip(targets, items)),
            "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    rows = [_normalize(t, items) for t, items in raw.get("results", [])]
    at_risk = sum(1 for r in rows if r["risk_level"] in ("high", "critical"))
    return {"scanned_at": raw.get("scanned_at"), "hosts_total": len(rows),
            "at_risk": at_risk, "rows": rows}


def schema() -> dict:
    return {
        "title": "Netlas Intel",
        "icon": "/icons/security/icons8-web-shield-50.png",
        "category": "api",
        "summary_keys": ["hosts_total", "at_risk"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "target", "label": "Target"},
                {"key": "risk_level", "label": "Risk", "badge": True},
                {"key": "risk_score", "label": "Score"},
                {"key": "open_ports", "label": "Ports"},
                {"key": "vuln_count", "label": "Vulns"},
            ],
        },
    }
