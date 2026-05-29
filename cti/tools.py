"""
tools.py — allowlisted read-only network diagnostics, runnable from the browser.

The L0 ("essentials") status pages let you reach for a tool right where you are:
a reverse DNS lookup next to the THC recon engine, a whois next to the BGP watch.
That power is dangerous, so it is fenced hard:

  - fixed allowlist of binaries (no arbitrary command, ever)
  - arguments are passed as an argv *list* to exec — never a shell string
  - the target is matched against one strict regex before it can reach exec
  - every run is bounded by a timeout and its output is capped

If a binary is not installed (e.g. dig/mtr on a bare host) the tool simply reports
"not available" instead of failing — the dashboard stays honest about what it can do.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time

log = logging.getLogger("cti.tools")

# A hostname, IPv4/IPv6, AS-number or CIDR prefix. Deliberately tight: letters,
# digits, dot, colon, hyphen and slash only — no spaces, semicolons, pipes, $,
# backticks. (Slash is safe: args go to exec as a list, never through a shell.)
_TARGET_RE = re.compile(r"^(\.|[A-Za-z0-9][A-Za-z0-9._:/-]{0,253})$")
_QTYPE_RE = re.compile(r"^[A-Za-z]{1,10}$")

_TIMEOUT = 15.0
_MAX_OUTPUT = 12000  # chars

ToolBuilder = "callable(target, extra) -> list[str]"


def _dig(target: str, extra: str | None) -> list[str]:
    qtype = (extra or "A").upper()
    return ["dig", "+nocmd", "+noall", "+answer", "+comments", "+stats", target, qtype]


def _whois(target: str, extra: str | None) -> list[str]:
    return ["whois", target]


def _host(target: str, extra: str | None) -> list[str]:
    return ["host", target]


def _mtr(target: str, extra: str | None) -> list[str]:
    return ["mtr", "--report", "--report-cycles", "3", "--no-dns", target]


def _traceroute(target: str, extra: str | None) -> list[str]:
    return ["traceroute", "-n", "-q", "1", "-w", "2", "-m", "15", target]


# name -> (binary, builder, extra_kind, label, hint)
#   extra_kind: None | "qtype" | "port"
TOOLS: dict[str, dict] = {
    "dig": {"bin": "dig", "build": _dig, "extra": "qtype",
            "label": "dig", "hint": "DNS record lookup (A/AAAA/NS/SOA/MX/TXT/PTR)"},
    "whois": {"bin": "whois", "build": _whois, "extra": None,
              "label": "whois", "hint": "registry record for a domain, IP or AS"},
    "host": {"bin": "host", "build": _host, "extra": None,
             "label": "host", "hint": "quick forward/reverse DNS resolution"},
    "mtr": {"bin": "mtr", "build": _mtr, "extra": None,
            "label": "mtr", "hint": "per-hop loss/latency report (3 cycles)"},
    "traceroute": {"bin": "traceroute", "build": _traceroute, "extra": None,
                   "label": "traceroute", "hint": "L3 path to the target (max 15 hops)"},
    # builtin — no external binary, implemented with asyncio below
    "tcp": {"bin": None, "build": None, "extra": "port",
            "label": "tcp-check", "hint": "connect-only TCP handshake to host:port"},
}


def available() -> list[dict]:
    """Descriptors for every tool, with whether its binary is installed."""
    out = []
    for name, t in TOOLS.items():
        ok = True if t["bin"] is None else shutil.which(t["bin"]) is not None
        out.append({"name": name, "label": t["label"], "hint": t["hint"],
                    "extra": t["extra"], "available": ok})
    return out


def _validate(name: str, target: str, extra: str | None) -> str | None:
    """Return an error string if the request is rejected, else None."""
    if name not in TOOLS:
        return f"unknown tool: {name}"
    if not target or not _TARGET_RE.match(target):
        return "invalid target (allowed: letters, digits, dot, colon, hyphen)"
    kind = TOOLS[name]["extra"]
    if kind == "qtype" and extra and not _QTYPE_RE.match(extra):
        return "invalid record type"
    if kind == "port":
        try:
            p = int(extra or "0")
        except ValueError:
            return "invalid port"
        if not (1 <= p <= 65535):
            return "port out of range (1-65535)"
    return None


async def _tcp_check(host: str, port: int) -> dict:
    start = time.time()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=_TIMEOUT)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        ms = round((time.time() - start) * 1000, 1)
        return {"ok": True, "output": f"open  {host}:{port}  ({ms} ms)"}
    except Exception as exc:
        ms = round((time.time() - start) * 1000, 1)
        return {"ok": False, "output": f"closed/filtered  {host}:{port}  ({type(exc).__name__}, {ms} ms)"}


async def run(name: str, target: str, extra: str | None = None) -> dict:
    """Run one allowlisted tool. Never raises for tool/usage errors — returns a
    dict with ok/output/error so the route can always answer 200 with detail."""
    target = (target or "").strip()
    extra = (extra or "").strip() or None

    err = _validate(name, target, extra)
    if err:
        return {"ok": False, "tool": name, "target": target, "error": err}

    if name == "tcp":
        res = await _tcp_check(target, int(extra))
        return {"tool": name, "target": f"{target}:{extra}", "cmd": f"tcp-connect {target}:{extra}", **res}

    spec = TOOLS[name]
    if shutil.which(spec["bin"]) is None:
        return {"ok": False, "tool": name, "target": target,
                "error": f"{spec['bin']} not installed on this host"}

    argv = spec["build"](target, extra)
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "tool": name, "target": target,
                    "cmd": " ".join(argv), "error": f"timed out after {int(_TIMEOUT)}s"}
        text = out.decode("utf-8", errors="replace")
        if len(text) > _MAX_OUTPUT:
            text = text[:_MAX_OUTPUT] + "\n… (truncated)"
        ms = round((time.time() - start) * 1000, 1)
        return {"ok": proc.returncode == 0, "tool": name, "target": target,
                "cmd": " ".join(argv), "rc": proc.returncode,
                "duration_ms": ms, "output": text.strip()}
    except Exception as exc:
        log.warning("tool %s failed: %s", name, exc)
        return {"ok": False, "tool": name, "target": target,
                "cmd": " ".join(argv), "error": str(exc)[:200]}
