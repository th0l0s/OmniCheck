"""
thc_rdns — DNS recon suite: co-hosting via ip.thc.org, CNAME chains,
PTR records, and passive subdomain discovery via crt.sh cert transparency.

  co_hosting  : per-IP co-hosting count (ip.thc.org) — no API key, free
  cname       : CNAME chain for each monitored domain (Cloudflare DoH)
  ptr         : PTR (reverse DNS) for each monitored IP (Cloudflare DoH)
  subdomains  : passive subdomain enum via crt.sh cert transparency
"""
from __future__ import annotations

import asyncio
import logging
import re
import socket
from datetime import datetime, timezone

log = logging.getLogger("cti.thc_rdns")

ID = "thc_rdns"
NAME = "THC DNS Recon"
INTERVAL = 86400  # daily — data stable; rate limit ~0.5 req/s

THC_BASE = "https://ip.thc.org"
DOH_BASE = "https://cloudflare-dns.com/dns-query"
CRTSH_BASE = "https://crt.sh"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_DOH_QTYPES = {"A": 1, "CNAME": 5, "PTR": 12}


def _strip(s: str) -> str:
    return _ANSI_RE.sub("", s).strip()


def _parse_cohost_response(text: str) -> dict:
    """Parse ip.thc.org ANSI text response into structured data."""
    asn = org = city = country = None
    total_domains = 0
    sample: list[str] = []

    for raw in text.splitlines():
        line = _strip(raw)
        if not line:
            continue
        if line.startswith(";;Entries:"):
            m = re.match(r";;Entries:\s*\d+/(\d+)", line)
            if m:
                total_domains = int(m.group(1))
        elif line.startswith(";ASN"):
            m = re.match(r";ASN\s*:\s*(\d+)", line)
            if m:
                asn = int(m.group(1))
        elif line.startswith(";Org"):
            m = re.match(r";Org\s*:\s*(.+)", line)
            if m:
                org = m.group(1).strip()
        elif line.startswith(";City"):
            m = re.match(r";City\s*:\s*(.+)", line)
            if m and m.group(1).strip() != "N/A":
                city = m.group(1).strip()
        elif line.startswith(";Country"):
            m = re.match(r";Country\s*:\s*(.+)", line)
            if m and m.group(1).strip() != "N/A":
                country = m.group(1).strip()
        elif not line.startswith(";") and len(sample) < 8:
            sample.append(line)

    return {"asn": asn, "org": org, "city": city, "country": country,
            "domain_count": total_domains, "sample_domains": sample}


async def _resolve_ip(domain: str) -> str | None:
    """Resolve domain name to first IPv4."""
    try:
        loop = asyncio.get_running_loop()
        infos = await asyncio.wait_for(
            loop.getaddrinfo(domain, None, family=socket.AF_INET), timeout=4.0)
        return infos[0][4][0] if infos else None
    except Exception:
        return None


async def _query_cohosting(client, target: str, resolved_ip: str | None) -> dict:
    ip = resolved_ip or target
    url = f"{THC_BASE}/{ip}"
    try:
        r = await client.get(url, timeout=20.0,
                             headers={"Accept": "text/plain", "User-Agent": "CTI-Sentinel/1.0"})
        r.raise_for_status()
        data = _parse_cohost_response(r.text)
    except Exception as exc:
        log.warning("thc_rdns %s failed: %s", ip, exc)
        data = {"asn": None, "org": None, "city": None, "country": None,
                "domain_count": None, "sample_domains": [], "error": str(exc)[:120]}
    data["target"] = target
    data["resolved_ip"] = resolved_ip if resolved_ip else ip
    return data


async def _doh_query(client, name: str, qtype: str) -> list[str]:
    """DNS-over-HTTPS via Cloudflare JSON API. Returns rdata strings."""
    try:
        r = await client.get(DOH_BASE,
                             params={"name": name, "type": qtype},
                             headers={"Accept": "application/dns-json"},
                             timeout=8.0)
        r.raise_for_status()
        js = r.json()
        want = _DOH_QTYPES.get(qtype.upper(), 0)
        return [a["data"] for a in (js.get("Answer") or []) if a.get("type") == want]
    except Exception as exc:
        log.debug("doh %s %s: %s", qtype, name, exc)
        return []


def _ip_to_arpa(ip: str) -> str:
    return ".".join(reversed(ip.split("."))) + ".in-addr.arpa"


async def _query_cname(client, domain: str) -> dict:
    """Follow CNAME chain up to 8 hops."""
    chain: list[str] = []
    current = domain
    for _ in range(8):
        answers = await _doh_query(client, current, "CNAME")
        if not answers:
            break
        target = answers[0].rstrip(".")
        chain.append(target)
        current = target
    return {"domain": domain, "chain": chain, "depth": len(chain)}


async def _query_ptr(client, ip: str) -> dict:
    """PTR record for an IP via DoH."""
    answers = await _doh_query(client, _ip_to_arpa(ip), "PTR")
    ptr = answers[0].rstrip(".") if answers else None
    return {"ip": ip, "ptr": ptr}


async def _query_subdomains(client, domain: str) -> dict:
    """Passive subdomain discovery via crt.sh certificate transparency."""
    try:
        r = await client.get(CRTSH_BASE,
                             params={"q": f"%.{domain}", "output": "json"},
                             timeout=30.0)
        r.raise_for_status()
        entries = r.json()
        subs: set[str] = set()
        for e in entries:
            for name in (e.get("name_value") or "").split("\n"):
                name = name.strip().lower().lstrip("*.")
                if name and name.endswith(domain) and name != domain:
                    subs.add(name)
        return {"domain": domain, "subdomains": sorted(subs), "count": len(subs)}
    except Exception as exc:
        log.warning("crtsh %s: %s", domain, exc)
        return {"domain": domain, "subdomains": [], "count": 0, "error": str(exc)[:120]}


# ── source contract ───────────────────────────────────────────────────────────

async def fetch(cfg, ctx) -> dict:
    from .. import targets as tgt
    import ipaddress

    data = tgt.load()
    ips = data["ips"]
    domains = data["domains"]
    all_tgts = ips + domains

    if not all_tgts:
        return {"cohosting": [], "cname": [], "ptr": [], "subdomains": [],
                "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    # resolve domains to IPs for co-hosting queries
    async def _prep(t: str) -> tuple[str, str | None]:
        try:
            ipaddress.ip_address(t)
            return t, None
        except ValueError:
            ip = await _resolve_ip(t)
            return t, ip

    preps = await asyncio.gather(*[_prep(t) for t in all_tgts])

    # co-hosting — stagger to respect ~0.5 req/s rate limit
    cohosting = []
    for i, (target, resolved_ip) in enumerate(preps):
        if i > 0:
            await asyncio.sleep(0.1)
        cohosting.append(await _query_cohosting(ctx.client, target, resolved_ip))

    # CNAME chains (domains only)
    cname = await asyncio.gather(*[_query_cname(ctx.client, d) for d in domains])

    # PTR records (IPs only)
    ptr = await asyncio.gather(*[_query_ptr(ctx.client, ip) for ip in ips])

    # subdomain discovery (domains only)
    subdomains = await asyncio.gather(*[_query_subdomains(ctx.client, d) for d in domains])

    return {
        "cohosting": cohosting,
        "cname": list(cname),
        "ptr": list(ptr),
        "subdomains": list(subdomains),
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _cohost_level(count) -> str:
    if count is None:
        return "error"
    if count == 0:
        return "dedicated"
    if count <= 5:
        return "low"
    if count <= 100:
        return "medium"
    if count <= 10000:
        return "high"
    return "cdn"


def parse(raw: dict) -> dict:
    cohost_rows = []
    for r in raw.get("cohosting", []):
        count = r.get("domain_count")
        cohost_rows.append({
            "target": r["target"],
            "resolved_ip": r.get("resolved_ip", "—"),
            "asn": r.get("asn") or "—",
            "org": r.get("org") or "—",
            "country": r.get("country") or "—",
            "domain_count": count if count is not None else "—",
            "cohost_level": _cohost_level(count),
            "sample_domains": ", ".join(r.get("sample_domains", [])[:5]),
            "error": r.get("error", ""),
        })

    cname_rows = []
    for r in raw.get("cname", []):
        cname_rows.append({
            "domain": r["domain"],
            "chain": " → ".join(r["chain"]) if r.get("chain") else "—",
            "depth": r.get("depth", 0),
        })

    ptr_rows = []
    for r in raw.get("ptr", []):
        ptr_rows.append({
            "ip": r["ip"],
            "ptr": r.get("ptr") or "—",
        })

    sub_rows = []
    for r in raw.get("subdomains", []):
        subs = r.get("subdomains", [])
        if subs:
            for s in subs:
                sub_rows.append({"domain": r["domain"], "subdomain": s})
        else:
            sub_rows.append({"domain": r["domain"], "subdomain": r.get("error") or "—"})

    return {
        "scanned_at": raw.get("scanned_at"),
        "targets_total": len(raw.get("cohosting", [])),
        "cohost_rows": cohost_rows,
        "cname_rows": cname_rows,
        "ptr_rows": ptr_rows,
        "sub_rows": sub_rows,
    }


def schema() -> dict:
    return {
        "title": "THC DNS Recon",
        "icon": "/icons/network/icons8-dns-50.png",
        "category": "probe",
        "domain_filter": True,
        "summary_keys": ["targets_total"],
        "sections": [
            {
                "title": "Co-Hosting (ip.thc.org)",
                "table": {
                    "rows_key": "cohost_rows",
                    "filter_key": "target",
                    "columns": [
                        {"key": "target", "label": "Target"},
                        {"key": "resolved_ip", "label": "IP"},
                        {"key": "asn", "label": "ASN"},
                        {"key": "org", "label": "Org"},
                        {"key": "country", "label": "Country"},
                        {"key": "domain_count", "label": "Co-Hosted"},
                        {"key": "cohost_level", "label": "Level", "badge": True},
                        {"key": "sample_domains", "label": "Samples"},
                    ],
                },
            },
            {
                "title": "CNAME Chains",
                "table": {
                    "rows_key": "cname_rows",
                    "filter_key": "domain",
                    "columns": [
                        {"key": "domain", "label": "Domain"},
                        {"key": "chain", "label": "CNAME Chain"},
                        {"key": "depth", "label": "Depth"},
                    ],
                },
            },
            {
                "title": "Reverse DNS (PTR)",
                "table": {
                    "rows_key": "ptr_rows",
                    "columns": [
                        {"key": "ip", "label": "IP"},
                        {"key": "ptr", "label": "PTR Record"},
                    ],
                },
            },
            {
                "title": "Subdomains (crt.sh)",
                "table": {
                    "rows_key": "sub_rows",
                    "filter_key": "domain",
                    "columns": [
                        {"key": "domain", "label": "Domain"},
                        {"key": "subdomain", "label": "Subdomain"},
                    ],
                },
            },
        ],
    }
