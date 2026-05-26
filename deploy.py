#!/usr/bin/env python3
"""
deploy.py — sync the consolidated `cti` app to the remote test host and restart.

Replaces the old multi-service deploy: there is one app, one unit (`cti`), one
config. This script syncs changed files, optionally upgrades deps, restarts the
service and verifies /api/health. It never deletes anything on the remote.

Usage:
  python deploy.py                 # sync changed files + restart cti
  python deploy.py --dry-run       # show what would change, upload nothing
  python deploy.py --pip           # also pip install -r requirements.txt
  python deploy.py --status        # just show remote health, no changes
  python deploy.py --logs [N]      # tail N lines of the cti journal (default 40)

Credentials via environment (never hardcoded):
  CTI_SSH_HOST  (default 100.120.138.71)   CTI_SSH_PORT (default 22)
  CTI_SSH_USER  (default root)             CTI_SSH_KEY  (private key path, preferred)
  CTI_SSH_PASS  (password fallback)
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import os
import sys
import time
from pathlib import Path

import paramiko

HOST = os.getenv("CTI_SSH_HOST", "100.120.138.71")
PORT = int(os.getenv("CTI_SSH_PORT", "22"))
USER = os.getenv("CTI_SSH_USER", "root")
KEY = os.getenv("CTI_SSH_KEY", "")
PASS = os.getenv("CTI_SSH_PASS", "")

LOCAL_ROOT = Path(__file__).resolve().parent
REMOTE_ROOT = "/opt/cti"
VENV = "/opt/cti/.venv"
SERVICE = "cti"
HEALTH_URL = "http://127.0.0.1:9000/api/health"

# What to sync: the app package, the unit/deps, the design assets, feeds.
# config.yaml is intentionally NOT synced — it is host-specific (real targets,
# enabled flags) and managed on the remote, like .env. Edit it there.
SYNC_DIRS = ["cti", "design"]
SYNC_FILES = ["cti.service", "requirements.txt", "README.md", "feeds.yaml"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", "logs", ".venv", "venv", ".git"}
SKIP_SUFFIX = {".pyc", ".pyo"}
# Never push local secrets/state/host config.
SKIP_NAMES = {".env", "targets.json", "config.yaml"}


def _skip(rel: Path) -> bool:
    return (any(p in SKIP_PARTS for p in rel.parts)
            or rel.suffix in SKIP_SUFFIX
            or rel.name in SKIP_NAMES)


def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(hostname=HOST, port=PORT, username=USER, timeout=15)
    if KEY:
        kw.update(key_filename=KEY, look_for_keys=False)
    elif PASS:
        kw.update(password=PASS, look_for_keys=False)
    else:
        kw["password"] = getpass.getpass(f"SSH password for {USER}@{HOST}: ")
    ssh.connect(**kw)
    return ssh, ssh.open_sftp()


def run(ssh, cmd):
    _, out, err = ssh.exec_command(cmd)
    rc = out.channel.recv_exit_status()
    return rc, out.read().decode(errors="replace").strip(), err.read().decode(errors="replace").strip()


def remote_md5(sftp, path):
    try:
        with sftp.open(path, "rb") as f:
            return _md5(f.read())
    except IOError:
        return None


def ensure_dir(sftp, path):
    parts = path.split("/")
    for i in range(2, len(parts) + 1):
        d = "/".join(parts[:i])
        if d:
            try:
                sftp.stat(d)
            except IOError:
                sftp.mkdir(d)


def collect():
    """(rel_posix, abs_path) for every file to consider."""
    items = []
    for d in SYNC_DIRS:
        base = LOCAL_ROOT / d
        if base.is_dir():
            for f in base.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(LOCAL_ROOT)
                    if not _skip(rel):
                        items.append((rel.as_posix(), f))
    for name in SYNC_FILES:
        f = LOCAL_ROOT / name
        if f.is_file():
            items.append((name, f))
    return items


def sync(sftp, dry):
    changed = 0
    for rel, abspath in sorted(collect()):
        content = abspath.read_bytes()
        rpath = f"{REMOTE_ROOT}/{rel}"
        if _md5(content) == remote_md5(sftp, rpath):
            continue
        changed += 1
        if dry:
            print(f"  [dry] {rel}")
            continue
        ensure_dir(sftp, rpath.rsplit("/", 1)[0])
        sftp.putfo(io.BytesIO(content), rpath)
        print(f"  sent  {rel}")
    return changed


def health(ssh):
    rc, out, _ = run(ssh, f"curl -s -m 10 {HEALTH_URL}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Deploy the cti app to the remote host.")
    ap.add_argument("--dry-run", action="store_true", help="show changes, upload nothing")
    ap.add_argument("--pip", action="store_true", help="pip install -r requirements.txt on remote")
    ap.add_argument("--status", action="store_true", help="show remote health and exit")
    ap.add_argument("--logs", nargs="?", const=40, type=int, help="tail N journal lines and exit")
    args = ap.parse_args()

    print(f"Connecting to {USER}@{HOST}:{PORT} …")
    ssh, sftp = connect()
    print("Connected.\n")
    try:
        if args.status:
            print(health(ssh) or "(no response)")
            return
        if args.logs is not None:
            _, out, _ = run(ssh, f"journalctl -u {SERVICE} -n {args.logs} --no-pager")
            print(out)
            return

        print(f"Syncing -> {REMOTE_ROOT}/")
        n = sync(sftp, args.dry_run)
        if args.dry_run:
            print(f"\n{n} file(s) would change.")
            return
        if n == 0 and not args.pip:
            print("Nothing changed — remote is up-to-date.")
            return
        print(f"{n} file(s) uploaded.")

        if args.pip:
            print("Installing requirements …")
            rc, _, err = run(ssh, f"{VENV}/bin/pip install -q -r {REMOTE_ROOT}/requirements.txt")
            print("  pip ok" if rc == 0 else f"  pip FAILED: {err[:300]}")

        print(f"Restarting {SERVICE} …")
        run(ssh, f"systemctl restart {SERVICE}")
        time.sleep(6)
        rc, state, _ = run(ssh, f"systemctl is-active {SERVICE}")
        print(f"  {SERVICE}: {state}")
        h = health(ssh)
        if h:
            import json
            try:
                d = json.loads(h)
                print(f"  health: {d['sources_ok']}/{d['sources_total']} sources ok")
            except Exception:
                print("  health:", h[:160])
        else:
            print("  [!] no health response — check `python deploy.py --logs`")
    finally:
        sftp.close()
        ssh.close()


if __name__ == "__main__":
    main()
