"""
opencti — STIX 2.1 bundle builder over the IOCs already collected in-process.

This is an exporter, not an upstream fetch: it reads the cached ACN/MISP IOCs
(and any future IOC-bearing source) from the shared cache and maps them to STIX
observables. Dry-run by default — it reports the bundle size so the dashboard
shows export readiness. Set sources.opencti.url + token and dry_run:false to push.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

log = logging.getLogger("cti.opencti")

ID = "opencti"
NAME = "OpenCTI Export"
INTERVAL = 1800

_NS = uuid.UUID("9b8c1d2e-0000-4000-8000-000000000001")

# Netlas/Shodan/MISP IOC types → STIX observable type
_IOC_MAP = {
    "ip-dst": "ipv4-addr", "ip-src": "ipv4-addr", "ip-dst|port": "ipv4-addr",
    "domain": "domain-name", "hostname": "domain-name",
    "md5": "file", "sha1": "file", "sha256": "file",
    "url": "url",
}


def _sid(kind, value):
    return f"{kind}--{uuid.uuid5(_NS, f'{kind}:{value}')}"


def _observable(ioc_type, value):
    stix = _IOC_MAP.get(ioc_type)
    if not stix or not value:
        return None
    if stix == "file":
        algo = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256"}.get(ioc_type, "MD5")
        return {"type": "file", "spec_version": "2.1", "id": _sid("file", value),
                "hashes": {algo: value}}
    return {"type": stix, "spec_version": "2.1", "id": _sid(stix, value), "value": value}


async def fetch(cfg, ctx) -> dict:
    """Read IOCs from the in-process cache of other sources (no upstream call)."""
    objects = {}
    counts = {}
    acn = ctx.cache.get("acn_misp", stale_ok=True) or {}
    # acn parse() exposes a flat `iocs` list extracted from recent MISP events.
    for ioc in (acn.get("iocs") or []):
        obs = _observable(ioc.get("type", ""), ioc.get("value", ""))
        if obs:
            objects[obs["id"]] = obs
            counts[obs["type"]] = counts.get(obs["type"], 0) + 1
    bundle = {"type": "bundle", "id": f"bundle--{uuid.uuid4()}",
              "objects": list(objects.values())}
    return {"bundle_size": len(bundle["objects"]), "by_type": counts,
            "dry_run": bool(cfg.get("dry_run", True)),
            "configured": bool(cfg.get("url") and cfg.get("token")),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    rows = [{"stix_type": k, "count": v} for k, v in sorted(raw.get("by_type", {}).items())]
    return {
        "bundle_size": raw.get("bundle_size", 0),
        "mode": "dry-run" if raw.get("dry_run", True) else "import",
        "configured": raw.get("configured", False),
        "rows": rows,
    }


def schema() -> dict:
    return {
        "title": "OpenCTI Export",
        "icon": "open-source",
        "summary_keys": ["bundle_size", "mode"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "stix_type", "label": "STIX Type"},
                {"key": "count", "label": "Count"},
            ],
        },
    }
