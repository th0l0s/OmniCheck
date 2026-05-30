"""Entrypoint: `python -m cti [command]`

  (no args)   start the server (uvicorn on host/port from config.yaml)
  setup       interactive wizard — configures assets_sources.yaml
  sync        one-shot asset sync from all configured sources, then exit
"""
from __future__ import annotations

import asyncio
import sys
import os

import uvicorn

from . import config


def _cmd_setup() -> None:
    from .setup_wizard import run_wizard
    run_wizard()


def _cmd_sync() -> None:
    import httpx
    from . import asset_sync

    async def _run():
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            result = await asset_sync.refresh(client)
        if result.get("skipped"):
            print("No assets_sources.yaml found — run 'python -m cti setup' first.")
        else:
            print(f"Sync done: {result['ips']} IPs, {result['domains']} domains "
                  f"(+{result['added']} new, {result['errors']} errors)")

    asyncio.run(_run())


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "setup":
        _cmd_setup()
        return
    if cmd == "sync":
        _cmd_sync()
        return
    if cmd and not cmd.startswith("-"):
        print(f"Unknown command: {cmd}\nUsage: python -m cti [setup|sync]", file=sys.stderr)
        sys.exit(1)

    cfg = config.load()
    host = os.getenv("CTI_HOST", cfg.get("host", "0.0.0.0"))
    port = int(os.getenv("CTI_PORT", cfg.get("port", 8000)))
    uvicorn.run("cti.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
