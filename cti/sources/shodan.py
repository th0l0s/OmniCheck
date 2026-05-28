"""
shodan — IP threat intel + risk scoring for the configured watchlist.

Requires sources.shodan.api_key and a non-empty targets list in config.yaml.
The blocking Shodan SDK runs in a thread pool. Risk model (max 100): critical
CVE +20 (cap 40), high +10 (cap 20), medium +5 (cap 10), sensitive port +15
(cap 45), high-risk tag +25, medium tag +10, port density +5 per 10 (cap 15).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("cti.shodan")

ID = "shodan"
NAME = "Shodan Intel"
INTERVAL = 86400  # daily — query credits are precious
REQUIRES = ["api_key"]

SENSITIVE_PORTS = {21, 22, 23, 25, 445, 139, 1433, 3306, 3389, 5432, 5900,
                   6379, 9200, 8080, 27017, 4444}
HIGH_RISK_TAGS = {"malware", "c2", "botnet", "ransomware"}
MEDIUM_RISK_TAGS = {"tor", "scanner", "honeypot", "compromised"}


def _severity(score):
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def _score(ports, vulns, tags):
    score, factors = 0, []
    tag_set = {t.lower() for t in tags}
    crit = sum(1 for v in vulns if v == "critical")
    high = sum(1 for v in vulns if v == "high")
    med = sum(1 for v in vulns if v == "medium")
    for n, pts_each, cap, label in [(crit, 20, 40, "critical"), (high, 10, 20, "high"),
                                    (med, 5, 10, "medium")]:
        pts = min(n * pts_each, cap)
        if pts:
            score += pts
            factors.append(f"{n} {label} CVE(s) (+{pts})")
    sensitive = [p for p in ports if p in SENSITIVE_PORTS]
    if sensitive:
        pts = min(len(sensitive) * 15, 45)
        score += pts
        factors.append(f"sensitive ports {sensitive} (+{pts})")
    for t in HIGH_RISK_TAGS & tag_set:
        score += 25
        factors.append(f"tag '{t}' (+25)")
    for t in MEDIUM_RISK_TAGS & tag_set:
        score += 10
        factors.append(f"tag '{t}' (+10)")
    density = min((len(ports) // 10) * 5, 15)
    if density:
        score += density
    score = min(score, 100)
    level = ("clean" if score == 0 else "low" if score <= 20 else "medium"
             if score <= 50 else "high" if score <= 75 else "critical")
    return score, level, factors


def _normalize(raw):
    ports = sorted({s.get("port") for s in raw.get("data", []) if s.get("port")})
    vuln_sev = []
    for cve, d in (raw.get("vulns", {}) or {}).items():
        cvss = d.get("cvss")
        if isinstance(cvss, dict):
            cvss = cvss.get("score")
        vuln_sev.append(_severity(float(cvss) if cvss is not None else None))
    tags = raw.get("tags", []) or []
    score, level, factors = _score(ports, vuln_sev, tags)
    return {"ip": raw.get("ip_str", ""), "open_ports": ports,
            "vuln_count": len(vuln_sev), "tags": tags,
            "country": raw.get("country_name"), "org": raw.get("org"),
            "risk_score": score, "risk_level": level, "factors": factors}


async def fetch(cfg, ctx) -> dict:
    from .. import targets as tgt
    import shodan as shodan_sdk
    api = shodan_sdk.Shodan(cfg["api_key"])
    # assets.yaml is the canonical source; config.yaml targets is a fallback
    targets = tgt.load()["ips"] or cfg.get("targets", [])
    loop = asyncio.get_event_loop()

    async def one(ip):
        try:
            return await loop.run_in_executor(None, api.host, ip)
        except Exception as exc:
            log.warning("shodan host %s failed: %s", ip, exc)
            return {"ip_str": ip, "_error": str(exc)[:120]}

    hosts = await asyncio.gather(*[one(ip) for ip in targets])
    return {"hosts": hosts, "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    rows = []
    for h in raw.get("hosts", []):
        if h.get("_error"):
            rows.append({"ip": h.get("ip_str", ""), "risk_level": "error",
                         "risk_score": None, "open_ports": "-", "vuln_count": "-",
                         "error": h["_error"]})
            continue
        n = _normalize(h)
        rows.append({"ip": n["ip"], "risk_level": n["risk_level"],
                     "risk_score": n["risk_score"],
                     "open_ports": len(n["open_ports"]), "vuln_count": n["vuln_count"],
                     "country": n["country"] or "", "org": n["org"] or ""})
    crit = sum(1 for r in rows if r["risk_level"] in ("high", "critical"))
    return {"scanned_at": raw.get("scanned_at"), "hosts_total": len(rows),
            "at_risk": crit, "rows": rows}


def schema() -> dict:
    return {
        "title": "Shodan Intel",
        "icon": "/icons/security/icons8-nmap-50.png",
        "category": "api",
        "summary_keys": ["hosts_total", "at_risk"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "ip", "label": "IP"},
                {"key": "risk_level", "label": "Risk", "badge": True},
                {"key": "risk_score", "label": "Score"},
                {"key": "open_ports", "label": "Ports"},
                {"key": "vuln_count", "label": "Vulns"},
                {"key": "country", "label": "Country"},
            ],
        },
    }
