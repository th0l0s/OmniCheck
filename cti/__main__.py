"""Entrypoint: `python -m cti`. No Docker, no gunicorn wrapper — uvicorn on Debian.

Host/port come from config.yaml (host/port keys), overridable via CTI_HOST/CTI_PORT.
"""
from __future__ import annotations

import os

import uvicorn

from . import config


def main() -> None:
    cfg = config.load()
    host = os.getenv("CTI_HOST", cfg.get("host", "0.0.0.0"))
    port = int(os.getenv("CTI_PORT", cfg.get("port", 8000)))
    uvicorn.run("cti.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
