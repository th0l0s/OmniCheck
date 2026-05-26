"""
atera — RMM alerts + tickets + offline servers from the Atera API.

Requires sources.atera.api_key. Pulls open alerts, open/triage tickets and
offline monitored servers in one sweep. Telegram dispatch from the old service
is intentionally dropped here — alerting belongs in a notifier, not a source.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("cti.atera")

ID = "atera"
NAME = "Atera RMM"
INTERVAL = 120
REQUIRES = ["api_key"]

BASE_URL = "https://app.atera.com"


async def _get(client, api_key, path, params):
    r = await client.get(f"{BASE_URL}{path}", params=params,
                         headers={"X-API-KEY": api_key, "Accept": "application/json"},
                         timeout=15.0)
    r.raise_for_status()
    return r.json().get("items", [])


async def fetch(cfg, ctx) -> dict:
    api_key = cfg["api_key"]
    alerts, tickets_open, tickets_triage, devices = await asyncio.gather(
        _get(ctx.client, api_key, "/api/v3/alerts", {"alertStatus": "Open", "itemsInPage": 50}),
        _get(ctx.client, api_key, "/api/v3/tickets", {"ticketStatus": "Open", "itemsInPage": 50}),
        _get(ctx.client, api_key, "/api/v3/tickets", {"ticketStatus": "Triage", "itemsInPage": 50}),
        _get(ctx.client, api_key, "/api/v3/devices",
             {"devicesTypes": "2", "status": "Monitored", "availabilities": "offline", "itemsInPage": 50}),
        return_exceptions=True,
    )
    if isinstance(alerts, Exception):
        raise alerts
    return {
        "alerts": alerts,
        "tickets_open": tickets_open if not isinstance(tickets_open, Exception) else [],
        "tickets_triage": tickets_triage if not isinstance(tickets_triage, Exception) else [],
        "devices_offline": devices if not isinstance(devices, Exception) else [],
    }


def parse(raw: dict) -> dict:
    alerts = raw.get("alerts", [])
    by_sev = {}
    for a in alerts:
        s = str(a.get("AlertSeverity", "")).strip() or "Unknown"
        by_sev[s] = by_sev.get(s, 0) + 1
    rows = [{"severity": str(a.get("AlertSeverity", "")), "title": a.get("Title", ""),
             "device": a.get("DeviceName", ""), "customer": a.get("CustomerName", ""),
             "device_type": str(a.get("AlertDeviceType", ""))} for a in alerts[:100]]
    return {
        "alerts_total": len(alerts),
        "tickets_open": len(raw.get("tickets_open", [])),
        "tickets_triage": len(raw.get("tickets_triage", [])),
        "servers_offline": len(raw.get("devices_offline", [])),
        "by_severity": by_sev,
        "rows": rows,
    }


def schema() -> dict:
    return {
        "title": "Atera RMM",
        "icon": "devices",
        "summary_keys": ["alerts_total", "tickets_open", "tickets_triage", "servers_offline"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "severity", "label": "Severity", "badge": True},
                {"key": "title", "label": "Alert"},
                {"key": "device", "label": "Device"},
                {"key": "customer", "label": "Customer"},
                {"key": "device_type", "label": "Type"},
            ],
        },
    }
