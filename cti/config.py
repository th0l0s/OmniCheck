"""
config.py — load config.yaml, expand ${ENV_VAR}, expose a plain dict.

One file holds every credential and cadence (no .env scattered across services).
Values may reference the environment with ${VAR}; missing vars expand to "".

config.yaml shape:
  debug: false
  host: 0.0.0.0
  port: 8000
  sources:
    shodan:
      enabled: true
      interval: 3600          # override the source's default cadence
      api_key: ${SHODAN_API_KEY}
      targets: ["8.8.8.8"]
    news_feed:
      enabled: true
      interval: 1800
    ...
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_RE = re.compile(r"\$\{([^}]+)\}")
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load(path: str | Path | None = None) -> dict:
    p = Path(path or os.getenv("CTI_CONFIG") or _DEFAULT_PATH)
    if not p.exists():
        return {"sources": {}}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return _expand(data)


def source_cfg(cfg: dict, source_id: str) -> dict:
    """Per-source config block, always a dict (empty if absent)."""
    return (cfg.get("sources") or {}).get(source_id) or {}
