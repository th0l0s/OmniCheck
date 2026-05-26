"""
Shared target loader for CTI monitoring engines.

Reads targets.json (or path in TARGETS_FILE env var) and returns
a flat list of target values (IPs, subnets, domains).

Usage in any engine:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from targets import load_targets
    WATCHLIST = load_targets()
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent / "targets.json"


def load_targets(path: str | None = None) -> list[str]:
    """Return flat list of target values from shared targets.json.

    Precedence: explicit path arg > TARGETS_FILE env var > targets.json next to this file.
    Returns empty list on any error (missing file, bad JSON) — engine still starts.
    """
    p = Path(path or os.getenv("TARGETS_FILE") or _DEFAULT_PATH)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        targets = [
            t["value"].strip()
            for t in data.get("targets", [])
            if isinstance(t, dict) and t.get("value", "").strip()
        ]
        log.info("targets: loaded %d from %s", len(targets), p)
        return targets
    except FileNotFoundError:
        log.warning("targets: file not found: %s — watchlist disabled", p)
        return []
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.error("targets: parse error in %s: %s", p, exc)
        return []
