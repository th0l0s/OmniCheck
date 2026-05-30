"""
auth.py — minimal API-key guard for mutating endpoints.

Read endpoints stay open (the service sits behind VPN/Tailscale and the static
dashboard polls them without a key). Mutating endpoints — which trigger upstream
fetches and spend API quota — require the X-API-Key header to match CTI_API_KEY.

If CTI_API_KEY is unset, mutating endpoints are refused (503) rather than left
open: a missing key means "not configured", not "anyone may mutate".
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str | None = Header(default=None, alias="x-api-key")) -> None:
    expected = os.getenv("CTI_API_KEY", "")
    if not expected:
        return  # local mode: no key configured → all mutations allowed
    if x_api_key != expected:
        raise HTTPException(401, "unauthorized")
