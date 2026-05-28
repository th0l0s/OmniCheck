"""
atera — RMM open tickets + recent alerts + offline servers from the Atera API.

Requires sources.atera.api_key. The dashboard shows OPEN TICKETS first, then
only the last 5 alerts (schema `sections`). Telegram dispatch from the old
service is intentionally dropped — alerting belongs in a notifier, not a source.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("cti.atera")

ID = "atera"
NAME = "Atera RMM"
INTERVAL = 120
REQUIRES = ["api_key"]
ICON = "/icons/tools/icons8-system-administrator-50.png"

BASE_URL = "https://app.atera.com"
ALERT_LIMIT = 5


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


def _ticket_row(t):
    return {
        "title": t.get("TicketTitle", "") or t.get("Title", ""),
        "customer": t.get("CustomerName", ""),
        "priority": t.get("TicketPriority", "") or t.get("TicketStatus", "Open"),
        "created": (t.get("TicketCreatedDate") or t.get("CreatedDate") or "")[:16].replace("T", " "),
    }


def _alert_row(a):
    return {
        "severity": str(a.get("AlertSeverity", "")),
        "title": a.get("Title", ""),
        "device": a.get("DeviceName", ""),
        "customer": a.get("CustomerName", ""),
        "created": (a.get("Created") or a.get("AlertCreatedDate") or "")[:16].replace("T", " "),
    }


def parse(raw: dict) -> dict:
    alerts = raw.get("alerts", [])
    tickets = raw.get("tickets_open", [])
    return {
        "tickets_open": len(tickets),
        "tickets_triage": len(raw.get("tickets_triage", [])),
        "alerts_total": len(alerts),
        "servers_offline": len(raw.get("devices_offline", [])),
        "ticket_rows": [_ticket_row(t) for t in tickets[:50]],
        "alert_rows": [_alert_row(a) for a in alerts[:ALERT_LIMIT]],
    }


def schema() -> dict:
    return {
        "title": "Atera RMM",
        "icon": ICON,
        "category": "api",
        "summary_keys": ["tickets_open", "tickets_triage", "alerts_total", "servers_offline"],
        "sections": [
            {"title": "Open Tickets", "table": {
                "rows_key": "ticket_rows",
                "columns": [
                    {"key": "title", "label": "Ticket"},
                    {"key": "customer", "label": "Customer"},
                    {"key": "priority", "label": "Priority", "badge": True},
                    {"key": "created", "label": "Created"},
                ]}},
            {"title": "Recent Alerts (last 5)", "table": {
                "rows_key": "alert_rows",
                "columns": [
                    {"key": "severity", "label": "Severity", "badge": True},
                    {"key": "title", "label": "Alert"},
                    {"key": "device", "label": "Device"},
                    {"key": "created", "label": "When"},
                ]}},
        ],
    }
