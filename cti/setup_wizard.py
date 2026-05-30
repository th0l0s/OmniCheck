"""
setup_wizard.py — interactive first-run configurator for asset sources.

Invoked by:  python -m cti setup

Writes assets_sources.yaml at the project root. Each source is either an
HTTP/S URL or a local file path; both return plain-text lists (one IP or
domain per line, # for comments). Manually-added assets are never removed
by the daily sync — sources only add, never delete.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_SOURCES_PATH = Path(__file__).resolve().parent.parent / "assets_sources.yaml"

_BANNER = """\
══════════════════════════════════════════════════════
  OmniCheck CTI — Asset Sources Setup
══════════════════════════════════════════════════════

  assets.yaml is refreshed daily from the sources you
  configure here. Each source is a plain-text file:
    · one IP or domain per line
    · lines starting with # are comments
    · blank lines are ignored
  Sources only ADD entries — manual additions in
  assets.yaml are always preserved.

  Supported:
    url   — http/https URL fetched at refresh time
    path  — absolute path to a local .txt file

  Press Enter at any prompt to skip it.
"""


def _ask(prompt: str) -> str:
    return input(f"  {prompt}: ").strip()


def _collect(kind: str) -> list[dict]:
    print(f"\n  ── {kind.upper()} sources ──────────────────────────────")
    sources: list[dict] = []
    while True:
        url  = _ask(f"URL for {kind} list (or Enter to skip)")
        path = _ask(f"Local path for {kind} .txt (or Enter to skip)")
        if url:
            sources.append({"url": url})
        if path:
            sources.append({"path": path})
        if not url and not path:
            break
        more = _ask("Add another source? [y/N]").lower()
        if more != "y":
            break
    return sources


def run_wizard() -> None:
    print(_BANNER)

    if _SOURCES_PATH.exists():
        ans = _ask("assets_sources.yaml already exists — overwrite? [y/N]").lower()
        if ans != "y":
            print("\n  Aborted — existing config left unchanged.\n")
            return

    ip_sources     = _collect("ips")
    domain_sources = _collect("domains")

    if not ip_sources and not domain_sources:
        print("\n  No sources entered — assets_sources.yaml not created.")
        print("  Run 'python -m cti setup' again when ready, or create")
        print(f"  {_SOURCES_PATH} manually.\n")
        return

    cfg: dict = {}
    if ip_sources:
        cfg["ips"] = ip_sources
    if domain_sources:
        cfg["domains"] = domain_sources

    header = (
        "# Asset sync sources — written by setup wizard\n"
        "# Edit freely. Refreshed daily while the server is running.\n"
        "# Run 'python -m cti sync' for an immediate refresh.\n"
        "#\n"
        "# Each entry: { url: https://... }  or  { path: /abs/path.txt }\n\n"
    )
    _SOURCES_PATH.write_text(
        header + yaml.safe_dump(cfg, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"\n  ✓ Written: {_SOURCES_PATH}")
    print("  Run 'python -m cti sync' for an immediate fetch.")
    print("  Daily auto-sync starts with the server.\n")
