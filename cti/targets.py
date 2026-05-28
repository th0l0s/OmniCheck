"""
targets.py — load and persist the monitored IP/domain watchlists.

Two flat lists in assets.yaml at the project root:
  ips:     [1.1.1.1, ...]      # queried by Shodan + Netlas
  domains: [one.one.one.one]   # queried by Netlas (host: queries)

Every intel engine reads from here. deploy.py never overwrites assets.yaml.
"""
from __future__ import annotations

import ipaddress
from pathlib import Path

import yaml

_PATH = Path(__file__).resolve().parent.parent / "assets.yaml"
_PATH_CWD = Path.cwd() / "assets.yaml"
_DEFAULTS: dict = {"ips": ["1.1.1.1"], "domains": ["one.one.one.one"]}


def _writable_path() -> Path:
    """Return the first path we can actually write to."""
    for p in (_PATH, _PATH_CWD):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
            return p
        except (OSError, PermissionError):
            continue
    raise OSError(f"Cannot write assets.yaml — tried {_PATH} and {_PATH_CWD}")


def load(path: Path | None = None) -> dict[str, list[str]]:
    """Return {'ips': [...], 'domains': [...]}. Falls back to hardcoded defaults."""
    p = path or _PATH
    if not p.exists():
        return {k: list(v) for k, v in _DEFAULTS.items()}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {
        "ips": [str(x).strip() for x in raw.get("ips", []) if str(x).strip()],
        "domains": [str(x).strip() for x in raw.get("domains", []) if str(x).strip()],
    }


def all_targets(path: Path | None = None) -> list[str]:
    t = load(path)
    return t["ips"] + t["domains"]


def classify(addr: str) -> str:
    """Return 'ip' or 'domain'."""
    try:
        ipaddress.ip_address(addr)
        return "ip"
    except ValueError:
        return "domain"


def save(ips: list[str], domains: list[str], path: Path | None = None) -> None:
    p = path or _writable_path()
    p.write_text(
        yaml.safe_dump(
            {"ips": sorted(set(ips)), "domains": sorted(set(domains))},
            default_flow_style=False, allow_unicode=True,
        ),
        encoding="utf-8",
    )
