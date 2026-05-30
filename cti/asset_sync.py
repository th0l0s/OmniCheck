"""
asset_sync.py — daily refresh of assets.yaml from external or local lists.

Source config lives in assets_sources.yaml at the project root:

  ips:
    - url: https://example.com/ips.txt   # one entry per line
    - path: /opt/lists/my-ips.txt
  domains:
    - url: https://feeds.example.com/domains.txt
    - path: /home/user/extra-domains.txt

Lines starting with # are comments; blank lines are ignored. IPs and domains
are classified automatically. Merge strategy: new entries from sources are
added, manually-added entries already in assets.yaml are never removed.

Run manually:  python -m cti sync
Auto-runs:     once per day while the server is up (main.py lifespan).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger("cti.asset_sync")

_SOURCES_PATH = Path(__file__).resolve().parent.parent / "assets_sources.yaml"
_SOURCES_CWD  = Path.cwd() / "assets_sources.yaml"

_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_IPV6 = re.compile(r"^[0-9a-fA-F:]{2,}:[0-9a-fA-F:]*$")


def _is_ip(s: str) -> bool:
    if _IPV4.match(s) and all(0 <= int(o) <= 255 for o in s.split(".")):
        return True
    return bool(_IPV6.match(s) and s.count(":") >= 2)


def _parse_lines(text: str) -> tuple[list[str], list[str]]:
    """Return (ips, domains) from a block of text — one entry per line."""
    ips, domains = [], []
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        if _is_ip(line):
            ips.append(line)
        elif "." in line and len(line) > 3 and " " not in line:
            domains.append(line)
    return ips, domains


def sources_path() -> Path | None:
    for p in (_SOURCES_PATH, _SOURCES_CWD):
        if p.exists():
            return p
    return None


def load_sources() -> dict:
    """Return the parsed assets_sources.yaml, or {} if absent."""
    p = sources_path()
    if not p:
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


async def _fetch_url(client, url: str) -> str:
    try:
        r = await client.get(url, timeout=15.0)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        log.warning("asset_sync: fetch %s failed — %s", url, exc)
        return ""


def _fetch_path(p: str) -> str:
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception as exc:
        log.warning("asset_sync: read %s failed — %s", p, exc)
        return ""


async def refresh(client) -> dict:
    """Fetch all sources, merge into assets.yaml. Returns a summary dict."""
    from . import targets as tgt

    sources = load_sources()
    if not sources:
        log.debug("asset_sync: no assets_sources.yaml — skipping")
        return {"skipped": True}

    new_ips: set[str] = set()
    new_domains: set[str] = set()
    errors = 0

    for entry in sources.get("ips", []):
        text = ""
        if "url" in entry:
            text = await _fetch_url(client, entry["url"])
        elif "path" in entry:
            text = _fetch_path(entry["path"])
        got_ips, _ = _parse_lines(text)
        new_ips.update(got_ips)
        if not text:
            errors += 1

    for entry in sources.get("domains", []):
        text = ""
        if "url" in entry:
            text = await _fetch_url(client, entry["url"])
        elif "path" in entry:
            text = _fetch_path(entry["path"])
        _, got_domains = _parse_lines(text)
        new_domains.update(got_domains)
        if not text:
            errors += 1

    current = tgt.load()
    merged_ips     = sorted(set(current["ips"])     | new_ips)
    merged_domains = sorted(set(current["domains"]) | new_domains)
    added = (len(merged_ips) - len(current["ips"])) + \
            (len(merged_domains) - len(current["domains"]))

    tgt.save(merged_ips, merged_domains)
    log.info("asset_sync: +%d new  (%d ips  %d domains)  %d source errors",
             added, len(merged_ips), len(merged_domains), errors)
    return {"ips": len(merged_ips), "domains": len(merged_domains),
            "added": added, "errors": errors}
