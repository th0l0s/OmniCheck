"""
store.py — tiny file-backed persistence. No DB, no Redis.

Keeps the last parsed payload per source so the dashboard is not empty after a
restart, and appends an events log for a light audit trail. Atomic writes via
tmp + os.replace. Location: ${CTI_STATE_DIR} or ./state next to the project.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("cti.store")

_DIR = Path(os.getenv("CTI_STATE_DIR", Path(__file__).resolve().parent.parent / "state"))
_CACHE_DIR = _DIR / "cache"
_EVENTS = _DIR / "events.jsonl"


def _ensure() -> bool:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as exc:
        log.warning("store dir unavailable (%s); persistence disabled", exc)
        return False


def write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, default=str), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_source(source_id: str, payload: Any) -> None:
    if _ensure():
        try:
            write_json(_CACHE_DIR / f"{source_id}.json", payload)
        except Exception as exc:
            log.warning("persist %s failed: %s", source_id, exc)


def load_source(source_id: str) -> Any:
    return read_json(_CACHE_DIR / f"{source_id}.json", default=None)


_FIRST_SEEN = _DIR / "first_seen.json"


def load_first_seen() -> dict:
    return read_json(_FIRST_SEEN, default={})


def save_first_seen(data: dict) -> None:
    if _ensure():
        try:
            write_json(_FIRST_SEEN, data)
        except Exception as exc:
            log.warning("save_first_seen failed: %s", exc)


def append_event(event: dict) -> None:
    if not _ensure():
        return
    try:
        event = {"ts": time.time(), **event}
        with _EVENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except Exception as exc:
        log.warning("append_event failed: %s", exc)


def tail_events(source_id: str | None = None, limit: int = 20) -> list[dict]:
    """Last `limit` events, newest first. Filtered to one source when given.

    Reads only the tail of the JSONL file so a long audit log stays cheap to
    serve. Lines that don't match the source are skipped after parsing."""
    if not _EVENTS.exists():
        return []
    try:
        # read a bounded tail of the file (events are short lines)
        with _EVENTS.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            window = min(size, 256 * 1024)
            f.seek(size - window)
            chunk = f.read().decode("utf-8", errors="replace")
        out: list[dict] = []
        for line in reversed(chunk.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if source_id and ev.get("source") != source_id:
                continue
            out.append(ev)
            if len(out) >= limit:
                break
        return out
    except Exception as exc:
        log.warning("tail_events failed: %s", exc)
        return []
