#!/usr/bin/env python3
"""
deploy.py — sync, install, and upgrade CTI Sentinel on the remote host.

  python deploy.py                  sync changed files + restart if anything changed
  python deploy.py --dry-run        show what would change, upload nothing
  python deploy.py --pip            sync + pip install -r requirements.txt + restart
  python deploy.py --force          sync + restart even if nothing changed
  python deploy.py --install        full bootstrap: apt / user / dirs / venv / service (idempotent)
  python deploy.py --status         show remote /api/health, no changes
  python deploy.py --logs [N]       tail N lines of cti journal (default 40)

Credentials via environment (never hardcoded):
  CTI_SSH_HOST  default 100.120.138.71    CTI_SSH_PORT  default 22
  CTI_SSH_USER  default root               CTI_SSH_KEY   private-key path (preferred)
  CTI_SSH_PASS  password fallback
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError:
    sys.exit("paramiko not found — install it: pip install paramiko")

# Windows consoles default to cp1252 and choke on the status glyphs (→ ↑ ✓).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── connection defaults ───────────────────────────────────────────────────────
HOST = os.getenv("CTI_SSH_HOST", "100.120.138.71")
PORT = int(os.getenv("CTI_SSH_PORT", "22"))
USER = os.getenv("CTI_SSH_USER", "root")
KEY  = os.getenv("CTI_SSH_KEY", "")
PASS = os.getenv("CTI_SSH_PASS", "")

# ── paths ─────────────────────────────────────────────────────────────────────
LOCAL_ROOT  = Path(__file__).resolve().parent
REMOTE_ROOT = "/opt/cti"
VENV        = "/opt/cti/.venv"
SERVICE     = "cti"
HEALTH_URL  = "http://127.0.0.1:9000/api/health"

# ── sync manifest ─────────────────────────────────────────────────────────────
# config.yaml and .env are never overwritten (host-specific).
# During --install they are pushed only if absent on the remote.
SYNC_DIRS   = ["cti"]
SYNC_FILES  = ["cti.service", "requirements.txt", "feeds.yaml", "README.md",
               "assets_sources.yaml.example"]
SKIP_PARTS  = {"__pycache__", ".pytest_cache", "logs", ".venv", "venv", ".git", "state"}
SKIP_SUFFIX = {".pyc", ".pyo"}
# These files are NEVER overwritten on the remote host — they contain
# instance-specific configuration, secrets, or user-managed data.
SKIP_NAMES  = {
    ".env",                     # API keys and secrets
    "config.yaml",              # host-specific ports, credentials, intervals
    "assets.yaml",              # user's monitored asset list
    "assets_sources.yaml",      # user's sync-source config (URLs / paths)
    "targets.json",             # legacy target list (older installs)
}

# ── .env template written on first install ────────────────────────────────────
_ENV_TEMPLATE = """\
# CTI Sentinel secrets — fill in the keys you use; leave the rest empty.
# Reload after editing: systemctl restart cti
CTI_API_KEY=
SHODAN_API_KEY=
NETLAS_API_KEY=
ATERA_API_KEY=
OPENCTI_URL=
OPENCTI_TOKEN=
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _skip(rel: Path) -> bool:
    return (any(p in SKIP_PARTS for p in rel.parts)
            or rel.suffix in SKIP_SUFFIX
            or rel.name in SKIP_NAMES)


def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


# ── SSH ───────────────────────────────────────────────────────────────────────

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw: dict = dict(hostname=HOST, port=PORT, username=USER, timeout=15)
    if KEY:
        kw.update(key_filename=KEY, look_for_keys=False)
    elif PASS:
        kw.update(password=PASS, look_for_keys=False)
    else:
        kw["password"] = getpass.getpass(f"SSH password for {USER}@{HOST}: ")
    ssh.connect(**kw)
    return ssh, ssh.open_sftp()


def run(ssh, cmd: str, check: bool = False) -> tuple[int, str, str]:
    _, out, err = ssh.exec_command(cmd)
    rc = out.channel.recv_exit_status()
    o  = out.read().decode(errors="replace").strip()
    e  = err.read().decode(errors="replace").strip()
    if check and rc != 0:
        raise RuntimeError(f"rc={rc}: {e or o}")
    return rc, o, e


def remote_md5(sftp, path: str) -> str | None:
    try:
        with sftp.open(path, "rb") as f:
            return _md5(f.read())
    except IOError:
        return None


def remote_exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except IOError:
        return False


def ensure_dir(sftp, path: str) -> None:
    parts = path.split("/")
    for i in range(2, len(parts) + 1):
        d = "/".join(parts[:i])
        if d:
            try:
                sftp.stat(d)
            except IOError:
                sftp.mkdir(d)


def put(sftp, content: bytes, rpath: str) -> None:
    ensure_dir(sftp, rpath.rsplit("/", 1)[0])
    sftp.putfo(io.BytesIO(content), rpath)


def _show_protected() -> None:
    print("  protected (never overwritten):", ", ".join(sorted(SKIP_NAMES)))


# ── file collection ───────────────────────────────────────────────────────────

def collect() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for d in SYNC_DIRS:
        base = LOCAL_ROOT / d
        if base.is_dir():
            for f in sorted(base.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(LOCAL_ROOT)
                    if not _skip(rel):
                        items.append((rel.as_posix(), f))
    for name in SYNC_FILES:
        f = LOCAL_ROOT / name
        if f.is_file():
            items.append((name, f))
    return items


# ── core operations ───────────────────────────────────────────────────────────

def sync(sftp, dry: bool = False, force: bool = False) -> int:
    """Upload files that differ from remote. Returns number of changes."""
    changed = 0
    for rel, abspath in collect():
        content = abspath.read_bytes()
        rpath   = f"{REMOTE_ROOT}/{rel}"
        if not force and _md5(content) == remote_md5(sftp, rpath):
            continue
        changed += 1
        if dry:
            print(f"  ~  {rel}")
            continue
        put(sftp, content, rpath)
        print(f"  ↑  {rel}")
    return changed


def pip_install(ssh) -> bool:
    print("  pip install -r requirements.txt …", end=" ", flush=True)
    rc, _, err = run(ssh, f"{VENV}/bin/pip install -q -r {REMOTE_ROOT}/requirements.txt")
    if rc == 0:
        print("ok")
        return True
    print(f"FAILED\n       {err[:300]}")
    return False


def restart(ssh) -> bool:
    rc, _, _ = run(ssh, f"systemctl restart {SERVICE}")
    time.sleep(5)
    _, state, _ = run(ssh, f"systemctl is-active {SERVICE}")
    ok = state.strip() == "active"
    print(f"  {'✓' if ok else '✗'}  {SERVICE}: {state.strip()}")
    return ok


def health_check(ssh) -> None:
    rc, out, _ = run(ssh, f"curl -s -m 10 {HEALTH_URL}")
    if not out:
        print("  [!] no health response — run --logs to investigate")
        return
    try:
        d = json.loads(out)
        print(f"  ✓  health: {d['sources_ok']}/{d['sources_total']} sources ok")
    except Exception:
        print("  health:", out[:160])


# ── install (bootstrap) ───────────────────────────────────────────────────────

def install(ssh, sftp, dry: bool) -> None:
    """Idempotent full bootstrap. Safe to re-run on an already-installed host."""

    def step(label: str, cmd: str) -> None:
        if dry:
            print(f"  [dry] {label}")
            return
        print(f"  →  {label} …", end=" ", flush=True)
        rc, out, err = run(ssh, cmd)
        if rc == 0:
            print("ok")
        else:
            msg = (err or out)[:200]
            print(f"FAILED (rc={rc})\n       {msg}")

    print("\n── system packages ──────────────────────────────────────────────────")
    step(
        "python3 + venv",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip 2>&1 | tail -2",
    )

    print("\n── service user ─────────────────────────────────────────────────────")
    step(
        "cti system user",
        "id cti &>/dev/null || useradd --system --home /opt/cti --shell /usr/sbin/nologin cti",
    )

    print("\n── directory structure ───────────────────────────────────────────────")
    step("mkdir /opt/cti/state/cache", "mkdir -p /opt/cti/state/cache")

    print("\n── file sync ─────────────────────────────────────────────────────────")
    n = sync(sftp, dry=dry)
    if not dry:
        print(f"  ✓  {n} file(s) changed")

    # config.yaml: push only on first install (never overwrite host-specific config)
    cfg_local  = LOCAL_ROOT / "config.yaml"
    cfg_remote = f"{REMOTE_ROOT}/config.yaml"
    if cfg_local.is_file():
        if dry:
            print("  [dry] config.yaml → push only if absent on remote")
        elif not remote_exists(sftp, cfg_remote):
            put(sftp, cfg_local.read_bytes(), cfg_remote)
            print("  ↑  config.yaml  (initial — edit targets + keys on remote)")
        else:
            print("  –  config.yaml  (kept — already present on remote)")

    print("\n── virtual environment ───────────────────────────────────────────────")
    step(f"python3 -m venv {VENV}", f"[ -d {VENV} ] || python3 -m venv {VENV}")
    step("pip install -r requirements.txt", f"{VENV}/bin/pip install -q -r {REMOTE_ROOT}/requirements.txt")

    print("\n── secrets file ─────────────────────────────────────────────────────")
    env_remote = f"{REMOTE_ROOT}/.env"
    if dry:
        print("  [dry] .env → create template if absent")
    elif not remote_exists(sftp, env_remote):
        put(sftp, _ENV_TEMPLATE.encode(), env_remote)
        run(ssh, f"chmod 600 {env_remote}")
        print("  ↑  .env  (template — fill in your API keys, then restart)")
    else:
        print("  –  .env  (kept — already present on remote)")

    print("\n── systemd unit ─────────────────────────────────────────────────────")
    step(
        "install cti.service",
        f"cp {REMOTE_ROOT}/cti.service /etc/systemd/system/cti.service && systemctl daemon-reload",
    )
    step(
        "enable + start",
        "systemctl enable cti && "
        "(systemctl is-active cti &>/dev/null && systemctl restart cti || systemctl start cti)",
    )

    print("\n── ownership ─────────────────────────────────────────────────────────")
    step(f"chown -R cti:cti {REMOTE_ROOT}", f"chown -R cti:cti {REMOTE_ROOT}")

    if not dry:
        print("\n── health ────────────────────────────────────────────────────────────")
        time.sleep(6)
        health_check(ssh)
    print()


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Deploy CTI Sentinel to the remote host.")
    ap.add_argument("--dry-run", action="store_true", help="show changes, upload nothing")
    ap.add_argument("--pip",     action="store_true", help="sync + pip install + restart")
    ap.add_argument("--upgrade", action="store_true", help="alias for --pip (sync + deps + restart)")
    ap.add_argument("--force",   action="store_true", help="sync + restart even if nothing changed")
    ap.add_argument("--install", action="store_true", help="full bootstrap (idempotent — safe to re-run)")
    ap.add_argument("--status",  action="store_true", help="show remote /api/health, no changes")
    ap.add_argument("--logs",    nargs="?", const=40, type=int, metavar="N",
                    help="tail N lines of cti journal (default 40)")
    ap.add_argument("--setup",   action="store_true",
                    help="run asset-sources setup wizard on the remote host")
    args = ap.parse_args()

    print(f"→ {USER}@{HOST}:{PORT}")
    ssh, sftp = connect()
    print("  connected\n")

    # --upgrade is a friendlier alias for --pip
    if args.upgrade:
        args.pip = True

    try:
        if args.status:
            health_check(ssh)
            return

        if args.logs is not None:
            _, out, _ = run(ssh, f"journalctl -u {SERVICE} -n {args.logs} --no-pager")
            print(out)
            return

        if args.setup:
            print("running setup wizard on remote …")
            _, out, err = run(ssh, f"cd {REMOTE_ROOT} && {VENV}/bin/python -m cti setup")
            print(out or err)
            return

        if args.install:
            install(ssh, sftp, dry=args.dry_run)
            return

        # ── normal sync / upgrade ──────────────────────────────────────────────
        _show_protected()
        print(f"syncing → {REMOTE_ROOT}/")
        n = sync(sftp, dry=args.dry_run, force=args.force)

        if args.dry_run:
            print(f"\n  {n} file(s) would change")
            return

        if n == 0 and not args.pip and not args.force:
            print("  remote is up-to-date")
            return

        print(f"  {n} file(s) uploaded")

        if args.pip:
            pip_install(ssh)

        print(f"\nrestarting {SERVICE} …")
        ok = restart(ssh)
        if ok:
            health_check(ssh)
        else:
            print("  run: python deploy.py --logs")

    finally:
        sftp.close()
        ssh.close()


if __name__ == "__main__":
    main()
