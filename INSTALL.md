# CTI Sentinel — Field Install Guide

> **Philosophy**: plant it in the ground, it runs forever.  
> One clone, one command, service auto-starts on boot. No Docker, no ceremony.

---

## Requirements

- Ubuntu 22.04+ (bare metal, VM, LXC, or WSL2)
- Python 3.11+ (`python3 --version`)
- systemd (skip the service step for WSL — use manual start instead)
- Internet access for API sources

---

## 1. Clone and enter

```bash
git clone https://github.com/YOUR/cti-sentinel /opt/cti
cd /opt/cti
```

Or copy the project folder to `/opt/cti` directly.

---

## 2. Create the virtual environment

```bash
python3 -m venv /opt/cti/.venv
/opt/cti/.venv/bin/pip install -q -r /opt/cti/requirements.txt
```

---

## 3. Configure API keys

```bash
cp /opt/cti/.env.example /opt/cti/.env   # or create from scratch
nano /opt/cti/.env
```

`.env` format:

```env
CTI_API_KEY=your-dashboard-key        # protects POST /api/targets if set
SHODAN_API_KEY=
NETLAS_API_KEY=
ATERA_API_KEY=
OPENCTI_URL=
OPENCTI_TOKEN=
```

Leave unused keys empty — those sources will auto-disable.

---

## 4. Set your monitored targets

```bash
nano /opt/cti/assets.yaml
```

```yaml
ips:
  - 1.2.3.4
domains:
  - example.com
```

You can also add/remove targets live from the dashboard without editing this file.

---

## 5a. Install as a systemd service (bare metal / VM / LXC)

```bash
cp /opt/cti/cti.service /etc/systemd/system/cti.service
systemctl daemon-reload
systemctl enable --now cti
systemctl status cti
```

Check it started:

```bash
curl -s http://127.0.0.1:9000/api/health | python3 -m json.tool
```

Logs:

```bash
journalctl -u cti -f
```

---

## 5b. WSL2 — manual start (no systemd by default)

WSL2 does not run systemd by default. Start the app in a tmux/screen session or
enable systemd in WSL2 (`/etc/wsl.conf`):

**Option A — background process:**

```bash
nohup /opt/cti/.venv/bin/python -m cti &
echo $! > /tmp/cti.pid
```

**Option B — enable systemd in WSL2** (Ubuntu 22.04+, persistent across reboots):

```ini
# /etc/wsl.conf
[boot]
systemd=true
```

Restart the WSL instance (`wsl --shutdown` from PowerShell), then use the
systemd steps above.

---

## 6. Access the dashboard

Open your browser: **http://localhost:9000** (or the server IP on port 9000).

The first load fetches live data — expect 10–30 s before all panels populate.

---

## Updating

```bash
cd /opt/cti
git pull
/opt/cti/.venv/bin/pip install -q -r requirements.txt
systemctl restart cti
```

Or use the deploy script from your dev machine:

```bash
python deploy.py --pip     # sync changed files + pip install + restart
python deploy.py --status  # check remote health
python deploy.py --logs    # tail service journal
```

---

## Directory layout

```
/opt/cti/
├── cti/              application code (auto-synced by deploy.py)
├── .venv/            Python virtual environment
├── .env              secrets — never committed, never overwritten
├── assets.yaml       monitored IPs and domains — host-specific
├── config.yaml       source settings — host-specific
├── cti.service       systemd unit
├── requirements.txt
└── state/
    └── cache/        persisted fetch results (JSON)
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Dashboard blank | `journalctl -u cti -n 50` |
| Source shows OFF | Missing key in `.env` — set it, then `systemctl restart cti` |
| Port conflict | Edit `config.yaml`: `port: 9001` |
| `No module named cti` | Activate venv: `/opt/cti/.venv/bin/python -m cti` |
| WSL — port not reachable from Windows | Use `localhost` or run `hostname -I` inside WSL |
