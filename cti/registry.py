"""
registry.py — discover source modules and track their live state.

A source is any module in cti.sources exposing the contract:
  ID:        str   unique slug
  NAME:      str   display name
  INTERVAL:  int   default refresh cadence (seconds)
  fetch(cfg, ctx) -> awaitable raw      pull from upstream
  parse(raw)      -> dict               normalise to dashboard shape
  schema()        -> dict               describe the UI tab (title, columns…)

Optional:
  REQUIRES:  list[str]   config keys that must be truthy or the source is skipped
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Optional

from . import sources as _sources_pkg

log = logging.getLogger("cti.registry")


@dataclass
class SourceState:
    module: Any
    id: str
    name: str
    interval: int
    enabled: bool = True
    last_fetch: Optional[str] = None   # ISO timestamp of last success
    last_error: Optional[str] = None
    age_s: Optional[float] = None
    ok: bool = False
    requires: list[str] = field(default_factory=list)

    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "ok": self.ok,
            "last_fetch": self.last_fetch,
            "age_s": self.age_s,
            "error": self.last_error,
            "interval": self.interval,
            "requires": self.requires,
        }


def discover() -> dict[str, SourceState]:
    """Import every module under cti/sources/ and register those that expose ID."""
    states: dict[str, SourceState] = {}
    for mod_info in pkgutil.iter_modules(_sources_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{_sources_pkg.__name__}.{mod_info.name}")
        sid = getattr(mod, "ID", None)
        if not sid:
            continue
        states[sid] = SourceState(
            module=mod,
            id=sid,
            name=getattr(mod, "NAME", sid),
            interval=int(getattr(mod, "INTERVAL", 600)),
            requires=list(getattr(mod, "REQUIRES", [])),
        )
        log.info("registered source: %s (%s)", sid, states[sid].name)
    return states
