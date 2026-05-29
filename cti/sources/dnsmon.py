"""
dnsmon — authoritative nameserver health monitor for domains in assets.yaml.

For each domain: resolves NS records via a recursive resolver, then queries
each NS directly for the SOA serial. Detects serial divergence across
nameservers the same way RIPE DNSmon does for root servers. Pure UDP DNS,
no external libraries. Reads domains from assets.yaml (via targets.py).
"""
from __future__ import annotations

import asyncio
import logging
import random
import socket
import struct
import time

log = logging.getLogger("cti.dnsmon")

ID = "dnsmon"
NAME = "Domain NS Monitor"
INTERVAL = 300

RESOLVER = "8.8.8.8"   # recursive resolver for NS lookups
PROBE_TIMEOUT = 3.0
QTYPE_NS, QTYPE_A, QTYPE_SOA, QCLASS_IN = 2, 1, 6, 1


# ── DNS wire helpers ──────────────────────────────────────────────────────────

def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        enc = label.encode()
        out += bytes([len(enc)]) + enc
    return out + b"\x00"


def _skip_name(data: bytes, off: int) -> int:
    while off < len(data):
        n = data[off]
        if n == 0:
            return off + 1
        if (n & 0xC0) == 0xC0:
            return off + 2
        off += 1 + n
    return off


def _read_name(data: bytes, off: int) -> tuple[str, int]:
    """Decode a DNS name, following pointers. Returns (name, new_offset)."""
    labels = []
    visited = set()
    jumped = False
    orig_off = off
    while off < len(data):
        n = data[off]
        if n == 0:
            if not jumped:
                orig_off = off + 1
            break
        if (n & 0xC0) == 0xC0:
            if off + 2 > len(data):
                break
            ptr = ((n & 0x3F) << 8) | data[off + 1]
            if ptr in visited:
                break
            visited.add(ptr)
            if not jumped:
                orig_off = off + 2
            off = ptr
            jumped = True
            continue
        label = data[off + 1:off + 1 + n].decode("ascii", errors="replace")
        labels.append(label)
        off += 1 + n
    return ".".join(labels), (orig_off if jumped else off + 1)


def _build_query(qname: str, qtype: int, rd: bool = True) -> tuple[int, bytes]:
    txid = random.randint(0, 0xFFFF)
    flags = 0x0100 if rd else 0x0000
    header = struct.pack("!HHHHHH", txid, flags, 1, 0, 0, 0)
    question = _encode_name(qname) + struct.pack("!HH", qtype, QCLASS_IN)
    return txid, header + question


class _UdpProto(asyncio.DatagramProtocol):
    def __init__(self, payload):
        self.payload = payload
        self.future = asyncio.get_running_loop().create_future()
        self.transport = None

    def connection_made(self, t):
        self.transport = t
        t.sendto(self.payload)

    def datagram_received(self, data, addr):
        if not self.future.done():
            self.future.set_result(data)
        if self.transport:
            self.transport.close()

    def error_received(self, exc):
        if not self.future.done():
            self.future.set_exception(exc)


async def _udp_query(ip: str, qname: str, qtype: int, rd: bool = True) -> bytes | None:
    txid, payload = _build_query(qname, qtype, rd)
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    try:
        loop = asyncio.get_running_loop()
        transport, proto = await loop.create_datagram_endpoint(
            lambda: _UdpProto(payload), remote_addr=(ip, 53), family=family)
        try:
            data = await asyncio.wait_for(proto.future, timeout=PROBE_TIMEOUT)
        finally:
            transport.close()
        # verify txid and QR bit
        if len(data) >= 4:
            rid = struct.unpack("!H", data[:2])[0]
            flags = struct.unpack("!H", data[2:4])[0]
            if rid == txid and (flags & 0x8000):
                return data
        return None
    except Exception:
        return None


def _parse_rr_list(data: bytes, off: int, count: int, want_type: int) -> list:
    """Parse `count` RRs starting at off, return rdata bytes for matching type."""
    results = []
    for _ in range(count):
        if off >= len(data):
            break
        off = _skip_name(data, off)
        if off + 10 > len(data):
            break
        rtype, _, _, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        if rtype == want_type:
            results.append(data[off:off + rdlen])
        off += rdlen
    return results


def _parse_ns_response(data: bytes) -> list[str]:
    """Extract NS hostnames from a DNS NS response."""
    if len(data) < 12:
        return []
    _, flags, qd, an, _, _ = struct.unpack("!HHHHHH", data[:12])
    if not (flags & 0x8000):
        return []
    off = 12
    for _ in range(qd):
        off = _skip_name(data, off)
        off += 4
    rdatas = _parse_rr_list(data, off, an, QTYPE_NS)
    names = []
    for rdata_off_bytes in rdatas:
        # rdata is the NS name, but we need absolute offset in data
        pass
    # simpler: re-parse using _read_name with full data context
    off = 12
    for _ in range(qd):
        off = _skip_name(data, off)
        off += 4
    ns_names = []
    for _ in range(an):
        if off >= len(data):
            break
        off = _skip_name(data, off)
        if off + 10 > len(data):
            break
        rtype, _, _, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        rdata_start = off + 10
        off += 10
        if rtype == QTYPE_NS:
            name, _ = _read_name(data, rdata_start)
            ns_names.append(name)
        off += rdlen
    return ns_names


def _parse_a_response(data: bytes) -> list[str]:
    """Extract A record IPs from a DNS A response."""
    if len(data) < 12:
        return []
    _, flags, qd, an, _, _ = struct.unpack("!HHHHHH", data[:12])
    if not (flags & 0x8000):
        return []
    off = 12
    for _ in range(qd):
        off = _skip_name(data, off)
        off += 4
    ips = []
    for _ in range(an):
        if off >= len(data):
            break
        off = _skip_name(data, off)
        if off + 10 > len(data):
            break
        rtype, _, _, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        if rtype == QTYPE_A and rdlen == 4:
            ips.append(socket.inet_ntoa(data[off:off + 4]))
        off += rdlen
    return ips


def _parse_soa_serial(data: bytes) -> int | None:
    """Extract SOA serial from the answer section."""
    if len(data) < 12:
        return None
    _, flags, qd, an, _, _ = struct.unpack("!HHHHHH", data[:12])
    if not (flags & 0x8000) or an == 0:
        return None
    off = 12
    for _ in range(qd):
        off = _skip_name(data, off)
        off += 4
    for _ in range(an):
        if off >= len(data):
            return None
        off = _skip_name(data, off)
        if off + 10 > len(data):
            return None
        rtype, _, _, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        rdata_start = off + 10
        off += 10
        if rtype == QTYPE_SOA:
            p = _skip_name(data, rdata_start)  # skip mname
            p = _skip_name(data, p)             # skip rname
            if p + 4 <= rdata_start + rdlen and p + 4 <= len(data):
                return struct.unpack("!I", data[p:p + 4])[0]
        off += rdlen
    return None


# ── per-domain probe ──────────────────────────────────────────────────────────

async def _probe_domain(domain: str) -> dict:
    start = time.time()
    # step 1 — resolve NS names via recursive resolver
    ns_resp = await _udp_query(RESOLVER, domain, QTYPE_NS)
    ns_names = _parse_ns_response(ns_resp) if ns_resp else []
    if not ns_names:
        return {"domain": domain, "status": "error", "error": "no NS found",
                "ns_count": 0, "serial": None, "serial_diverge": False,
                "ns_details": []}

    # step 2 — resolve each NS to an IP (use recursive resolver)
    ns_ips: dict[str, str] = {}
    for ns in ns_names[:8]:  # cap to avoid excessive queries
        a_resp = await _udp_query(RESOLVER, ns, QTYPE_A)
        ips = _parse_a_response(a_resp) if a_resp else []
        if ips:
            ns_ips[ns] = ips[0]

    # step 3 — query SOA from each NS directly (authoritative, RD=0)
    ns_details = []
    serials = {}
    for ns, ip in ns_ips.items():
        t0 = time.time()
        soa_resp = await _udp_query(ip, domain, QTYPE_SOA, rd=False)
        latency = round((time.time() - t0) * 1000, 1)
        serial = _parse_soa_serial(soa_resp) if soa_resp else None
        ok = serial is not None
        if ok:
            serials[ns] = serial
        ns_details.append({"ns": ns, "ip": ip, "ok": ok,
                            "serial": serial, "latency_ms": latency})

    serial_counts: dict[int, int] = {}
    for s in serials.values():
        serial_counts[s] = serial_counts.get(s, 0) + 1
    common_serial = max(serial_counts, key=serial_counts.get) if serial_counts else None
    diverge = len(serial_counts) > 1
    ok_count = sum(1 for d in ns_details if d["ok"])
    status = ("diverged" if diverge else
              "ok" if ok_count == len(ns_details) and ns_details else
              "warning" if ok_count else "critical")
    return {
        "domain": domain,
        "status": status,
        "ns_count": len(ns_names),
        "ns_ok": ok_count,
        "serial": common_serial,
        "serial_diverge": diverge,
        "latency_ms": round((time.time() - start) * 1000, 1),
        "ns_details": ns_details,
    }


# ── source contract ───────────────────────────────────────────────────────────

async def fetch(cfg, ctx) -> dict:
    from .. import targets as tgt
    domains = tgt.load().get("domains", []) or cfg.get("domains", [])
    if not domains:
        return {"domains": [], "scanned_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds")}
    results = await asyncio.gather(*[_probe_domain(d) for d in domains])
    from datetime import datetime, timezone
    return {"domains": list(results),
            "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def parse(raw: dict) -> dict:
    rows = raw.get("domains", [])
    at_risk = sum(1 for r in rows if r["status"] in ("critical", "diverged", "warning"))
    return {
        "scanned_at": raw.get("scanned_at"),
        "domains_total": len(rows),
        "at_risk": at_risk,
        "rows": [{
            "domain": r["domain"],
            "status": r["status"],
            "ns_count": r["ns_count"],
            "ns_ok": r.get("ns_ok", 0),
            "serial": r.get("serial"),
            "serial_diverge": r.get("serial_diverge", False),
            "latency_ms": r.get("latency_ms"),
        } for r in rows],
    }


def schema() -> dict:
    return {
        "title": "Domain NS Monitor",
        "icon": "/icons/network/icons8-domain-name-50.png",
        "category": "probe",
        "domain_filter": True,
        "summary_keys": ["domains_total", "at_risk"],
        "table": {
            "rows_key": "rows",
            "filter_key": "domain",
            "columns": [
                {"key": "domain", "label": "Domain"},
                {"key": "status", "label": "Status", "badge": True},
                {"key": "ns_count", "label": "NS"},
                {"key": "ns_ok", "label": "NS OK"},
                {"key": "serial", "label": "SOA Serial"},
                {"key": "serial_diverge", "label": "Diverged"},
                {"key": "latency_ms", "label": "ms"},
            ],
        },
        "tools": [
            {"tool": "dig", "label": "dig NS", "arg": "example.com", "extra": "NS"},
            {"tool": "dig", "label": "dig SOA", "arg": "example.com", "extra": "SOA"},
            {"tool": "whois", "label": "whois domain", "arg": "example.com"},
        ],
    }
