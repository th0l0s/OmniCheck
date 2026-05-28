# CTI Sentinel — Implant Guide

Step-by-step installation on a fresh Debian/Ubuntu host, designed to survive
subsequent `git pull` upgrades without touching local configuration.

---

## 1. Prerequisites

| Item | Requirement |
|------|-------------|
| OS | Debian 12+ / Ubuntu 22.04+ (or any systemd distro) |
| Python | 3.11+ (`python3 --version`) |
| pip | 24+ |
| git | any recent version |
| User | root or a dedicated `cti` service account |
| Network | outbound HTTPS (443) to query APIs and feeds |

Install system deps once:
```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

---

## 2. Choose an install path

```
/opt/cti/           ← application code  (git-managed, will be updated)
/opt/cti/state/     ← runtime state     (never overwritten)
/opt/cti/config.yaml ← your credentials (never overwritten by deploy.py)
/opt/cti/assets.yaml ← your watchlist   (never overwritten by deploy.py)
```

```bash
mkdir -p /opt/cti
cd /opt/cti
```

---

## 3. Clone the repository

```bash
git clone https://github.com/YOUR_USER/cti.git /opt/cti
cd /opt/cti
```

If you got a zip/tarball instead:
```bash
unzip cti.zip -d /opt/cti
cd /opt/cti
```

---

## 4. Create a virtual environment

```bash
python3 -m venv /opt/cti/.venv
source /opt/cti/.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify:
```bash
python -m cti --help   # should print usage or version, not traceback
```

---

## 5. Configure

Copy the example config and edit it:

```bash
cp config.example.yaml config.yaml   # if the example exists
# OR create from scratch:
cat > config.yaml << 'EOF'
host: 127.0.0.1
port: 9000

sources:
  shodan:
    api_key: ""          # paste your Shodan API key here, or leave blank to disable
  netlas:
    api_key: ""          # paste your Netlas API key here, or leave blank to disable
  atera:
    api_key: ""          # Atera API key, or leave blank to disable
    # customer_id: ""    # required if api_key is set

# debug: true            # uncomment for verbose logs
EOF
```

> **Rule**: `config.yaml` and `assets.yaml` are yours.  
> `git pull` never touches them. Neither does `deploy.py`.

Set the API key for the dashboard mutation endpoint (optional but recommended):
```bash
echo "CTI_API_KEY=$(openssl rand -hex 24)" >> /etc/environment
```

---

## 6. Add your watchlist

```bash
cat > assets.yaml << 'EOF'
ips:
  - 1.1.1.1
domains:
  - one.one.one.one
EOF
```

Edit this file freely at any time — the dashboard picks up changes on the next
refresh cycle without a restart.

---

## 7. First run (foreground test)

```bash
source /opt/cti/.venv/bin/activate
CTI_API_KEY=changeme python -m cti
```

Open `http://127.0.0.1:9000` in a browser. You should see the OMNI.CTI
dashboard with the health status bars populated.

Press `Ctrl+C` to stop when satisfied.

---

## 8. Install as a systemd service

```bash
cat > /etc/systemd/system/cti.service << 'EOF'
[Unit]
Description=CTI Sentinel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/cti
Environment="CTI_API_KEY=changeme"
ExecStart=/opt/cti/.venv/bin/python -m cti
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cti
systemctl start cti
```

Check status:
```bash
systemctl status cti
journalctl -u cti -f
```

Replace `CTI_API_KEY=changeme` with a real random key. To avoid the key
appearing in `ps` output or systemd show, put it in a DropIn:
```bash
mkdir -p /etc/systemd/system/cti.service.d
cat > /etc/systemd/system/cti.service.d/secrets.conf << 'EOF'
[Service]
Environment="CTI_API_KEY=YOUR_REAL_KEY_HERE"
EOF
systemctl daemon-reload && systemctl restart cti
```

---

## 9. Expose via reverse proxy (optional)

If you want HTTPS or a non-loopback bind, put nginx or Caddy in front:

```nginx
# /etc/nginx/sites-available/cti
server {
    listen 443 ssl;
    server_name cti.yourdomain.internal;
    ssl_certificate     /etc/ssl/certs/cti.crt;
    ssl_certificate_key /etc/ssl/private/cti.key;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Or simply change `host: 0.0.0.0` in `config.yaml` and bind to the Tailscale
interface for private network access.

---

## 10. Updating to a new release

The key principle: **only code is updated, never config or state**.

```bash
# 1. pull latest code
cd /opt/cti
git pull

# 2. install any new/updated Python dependencies
source .venv/bin/activate
pip install -r requirements.txt

# 3. restart the service — config.yaml and assets.yaml are untouched
systemctl restart cti

# 4. verify
systemctl status cti
```

`deploy.py` (included in the repo) automates steps 1–3 over SSH:
```bash
python deploy.py --host YOUR_HOST --user root
```

It copies only source code, runs `pip install`, then restarts the unit. It
explicitly skips `config.yaml`, `assets.yaml`, and `state/`.

---

## 11. Directory reference after install

```
/opt/cti/
├── cti/                ← application package (git-managed)
│   ├── sources/        ← one file per data source
│   └── static/         ← dashboard HTML (single file)
├── state/
│   ├── cache/          ← per-source JSON snapshots (auto-created)
│   ├── events.jsonl    ← lightweight audit log
│   └── first_seen.json ← asset insertion dates
├── .venv/              ← Python virtual environment
├── config.yaml         ← YOUR FILE — never overwritten
├── assets.yaml         ← YOUR FILE — never overwritten
├── feeds.yaml          ← curated RSS list (git-managed, safe to extend)
└── requirements.txt    ← pinned deps (git-managed)
```

---

## 12. Backup

Minimum backup set (everything that is yours):

```bash
tar czf cti-backup-$(date +%F).tar.gz \
  /opt/cti/config.yaml \
  /opt/cti/assets.yaml \
  /opt/cti/state/
```

Restore on a fresh install:
```bash
# 1. Follow steps 1–4 above
# 2. Extract your backup
tar xzf cti-backup-DATE.tar.gz -C /
# 3. Start the service
systemctl start cti
```

The state cache pre-warms the dashboard immediately after restart — no waiting
for all sources to refetch.

---

## 13. Troubleshooting

| Symptom | Check |
|---------|-------|
| Dashboard blank | `journalctl -u cti -n 50` for startup errors |
| Source shows OFF | Go to ⓘ STATUS tab — "Configuration issues" lists missing keys |
| Source shows ERR | ⓘ STATUS tab — "Runtime errors" with the last exception |
| Port already in use | `ss -tlnp | grep 9000` — change `port:` in config.yaml |
| API key prompts | Set `CTI_API_KEY` env var in the systemd DropIn (step 8) |
| Stale data after restart | Expected — state cache warms from disk in seconds |
