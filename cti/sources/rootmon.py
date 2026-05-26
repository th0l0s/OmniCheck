"""
rootmon — DNS root server liveness monitor (A–M), UDP SOA + TCP connect.

No credentials, no dnspython: a real DNS query for the root SOA over UDP and a
connect-only TCP handshake, timed per server. Root hints are fetched live from
IANA named.root with a static fallback so the probe always has targets.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import socket
import struct
import time

log = logging.getLogger("cti.rootmon")

ID = "rootmon"
NAME = "Root DNS Monitor"
INTERVAL = 120

ROOT_HINTS_URL = "https://www.internic.net/domain/named.root"
PROBE_TIMEOUT = 2.0
QTYPE_SOA, QCLASS_IN = 6, 1

_FALLBACK = [
    ("A", "a.root-servers.net", "198.41.0.4", "2001:503:ba3e::2:30"),
    ("B", "b.root-servers.net", "170.247.170.2", "2801:1b8:10::b"),
    ("C", "c.root-servers.net", "192.33.4.12", "2001:500:2::c"),
    ("D", "d.root-servers.net", "199.7.91.13", "2001:500:2d::d"),
    ("E", "e.root-servers.net", "192.203.230.10", "2001:500:a8::e"),
    ("F", "f.root-servers.net", "192.5.5.241", "2001:500:2f::f"),
    ("G", "g.root-servers.net", "192.112.36.4", "2001:500:12::d0d"),
    ("H", "h.root-servers.net", "198.97.190.53", "2001:500:1::53"),
    ("I", "i.root-servers.net", "192.36.148.17", "2001:7fe::53"),
    ("J", "j.root-servers.net", "192.58.128.30", "2001:503:c27::2:30"),
    ("K", "k.root-servers.net", "193.0.14.129", "2001:7fd::1"),
    ("L", "l.root-servers.net", "199.7.83.42", "2001:500:9f::42"),
    ("M", "m.root-servers.net", "202.12.27.33", "2001:dc3::35"),
]
_A_RE = re.compile(r"^([A-M])\.ROOT-SERVERS\.NET\.\s+\d+\s+IN\s+A\s+([0-9.]+)", re.I)
_AAAA_RE = re.compile(r"^([A-M])\.ROOT-SERVERS\.NET\.\s+\d+\s+IN\s+AAAA\s+([0-9a-f:]+)", re.I)


def _build_query():
    txid = random.randint(0, 0xFFFF)
    header = struct.pack("!HHHHHH", txid, 0x0000, 1, 0, 0, 0)
    question = b"\x00" + struct.pack("!HH", QTYPE_SOA, QCLASS_IN)  # qname "."
    return txid, header + question


def _parse_header(data, txid):
    if len(data) < 12:
        raise ValueError("short response")
    rid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    if rid != txid:
        raise ValueError("txid mismatch")
    if not (flags & 0x8000):
        raise ValueError("not a response")
    return {"rcode": flags & 0x000F, "ancount": an}


class _UdpProto(asyncio.DatagramProtocol):
    def __init__(self, payload):
        self.payload = payload
        self.future = asyncio.get_running_loop().create_future()
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        transport.sendto(self.payload)

    def datagram_received(self, data, addr):
        if not self.future.done():
            self.future.set_result(data)
        if self.transport:
            self.transport.close()

    def error_received(self, exc):
        if not self.future.done():
            self.future.set_exception(exc)


async def _probe_udp(ip, ver, letter, host):
    start = time.time()
    txid, payload = _build_query()
    family = socket.AF_INET6 if ver == 6 else socket.AF_INET
    try:
        loop = asyncio.get_running_loop()
        transport, proto = await loop.create_datagram_endpoint(
            lambda: _UdpProto(payload), remote_addr=(ip, 53), family=family)
        try:
            data = await asyncio.wait_for(proto.future, timeout=PROBE_TIMEOUT)
        finally:
            transport.close()
        parsed = _parse_header(data, txid)
        return {"target": letter, "ip": ip, "ip_version": ver, "protocol": "udp",
                "ok": parsed["rcode"] == 0, "latency_ms": round((time.time() - start) * 1000, 1),
                "rcode": parsed["rcode"]}
    except Exception as e:
        return {"target": letter, "ip": ip, "ip_version": ver, "protocol": "udp",
                "ok": False, "error": type(e).__name__}


async def _probe_tcp(ip, ver, letter, host):
    start = time.time()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 53),
                                                timeout=PROBE_TIMEOUT)
        writer.close()
        await writer.wait_closed()
        return {"target": letter, "ip": ip, "ip_version": ver, "protocol": "tcp-connect",
                "ok": True, "latency_ms": round((time.time() - start) * 1000, 1)}
    except Exception as e:
        return {"target": letter, "ip": ip, "ip_version": ver, "protocol": "tcp-connect",
                "ok": False, "error": type(e).__name__}


async def _hints(client):
    by_letter = {l: {"letter": l, "hostname": h, "ipv4": v4, "ipv6": v6, "source": "fallback"}
                 for l, h, v4, v6 in _FALLBACK}
    try:
        r = await client.get(ROOT_HINTS_URL, timeout=10.0)
        r.raise_for_status()
        for line in r.text.splitlines():
            line = line.strip()
            ma = _A_RE.match(line)
            if ma:
                by_letter[ma.group(1).upper()]["ipv4"] = ma.group(2)
            mb = _AAAA_RE.match(line)
            if mb:
                by_letter[mb.group(1).upper()]["ipv6"] = mb.group(2)
    except Exception as exc:
        log.warning("root hints fetch failed, using fallback: %s", exc)
    return [by_letter[k] for k in sorted(by_letter)]


async def fetch(cfg, ctx) -> dict:
    servers = await _hints(ctx.client)
    jobs = []
    for s in servers:
        if s["ipv4"]:
            jobs += [_probe_udp(s["ipv4"], 4, s["letter"], s["hostname"]),
                     _probe_tcp(s["ipv4"], 4, s["letter"], s["hostname"])]
        if s["ipv6"]:
            jobs += [_probe_udp(s["ipv6"], 6, s["letter"], s["hostname"]),
                     _probe_tcp(s["ipv6"], 6, s["letter"], s["hostname"])]
    results = await asyncio.gather(*jobs, return_exceptions=True)
    results = [r for r in results if isinstance(r, dict)]
    return {"servers": servers, "results": results}


def parse(raw: dict) -> dict:
    results = raw.get("results", [])
    total = len(results)
    ok = sum(1 for r in results if r.get("ok"))
    udp_ok = [r["latency_ms"] for r in results
              if r.get("protocol") == "udp" and r.get("ok") and r.get("latency_ms") is not None]
    rows = []
    for s in raw.get("servers", []):
        srv = [r for r in results if r["target"] == s["letter"]]
        up = sum(1 for r in srv if r.get("ok"))
        rows.append({"server": s["letter"], "hostname": s["hostname"],
                     "ipv4": s["ipv4"], "checks_ok": f"{up}/{len(srv)}",
                     "status": "ok" if up == len(srv) and srv else ("warning" if up else "critical")})
    return {
        "total_checks": total, "ok": ok, "fail": total - ok,
        "success_ratio": round(ok / total, 3) if total else 0,
        "avg_udp_latency_ms": round(sum(udp_ok) / len(udp_ok), 1) if udp_ok else None,
        "rows": rows,
    }


def schema() -> dict:
    return {
        "title": "Root DNS Monitor",
        "icon": "network",
        "summary_keys": ["total_checks", "ok", "fail", "avg_udp_latency_ms"],
        "table": {
            "rows_key": "rows",
            "columns": [
                {"key": "server", "label": "Root"},
                {"key": "hostname", "label": "Hostname"},
                {"key": "ipv4", "label": "IPv4"},
                {"key": "checks_ok", "label": "Checks OK"},
                {"key": "status", "label": "Status", "badge": True},
            ],
        },
    }
