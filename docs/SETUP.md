# OmniCheck / CTI Sentinel — First Setup

A single Python service: sources + scheduler + dashboard. No Docker, no Redis,
no DB. Runs on one Debian host behind your VPN/Tailscale.

## 1. Get the code + venv

```bash
git clone https://github.com/th0l0s/OmniCheck.git /opt/cti
cd /opt/cti
python3 -m venv .venv
.venv/bin/pip install -e .            # or: .venv/bin/pip install -r requirements.txt
```

## 2. Configure

`config.yaml` holds cadences and which sources are enabled. Secrets are referenced
as `${VAR}` and live in the environment / `.env` — never in the file.

```bash
cp /dev/null .env && chmod 600 .env
cat >> .env <<'EOF'
# API keys (only what you use)
SHODAN_API_KEY=...
NETLAS_API_KEY=...
ATERA_API_KEY=...
# Required to allow POST /api/refresh (mutating endpoint)
CTI_API_KEY=choose-a-long-random-string
EOF
```

Edit `config.yaml`:
- `host`: `127.0.0.1` (default, loopback) or `0.0.0.0` to expose on the VPN/LAN.
- per source: `enabled`, `interval`, and for shodan/netlas the `targets` list.

A source whose required keys are missing is **skipped** and shown as `off` in the
dashboard — the service still starts. Check the **Status** tab for what's missing.

## 3. Run

```bash
.venv/bin/python -m cti      # serves the dashboard on the configured host:port
```

Open `http://<host>:9000`.

## 4. Run as a service (hardened, non-root)

```bash
sudo useradd --system --home /opt/cti --shell /usr/sbin/nologin cti
sudo install -d -o cti -g cti /opt/cti/state
sudo chown -R cti:cti /opt/cti
sudo cp cti.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cti
journalctl -u cti -f
```

## 5. Deploy updates to the test host

From your workstation (credentials via `CTI_SSH_*` env):

```bash
python deploy.py --dry-run     # preview
python deploy.py               # sync changed files + restart + health check
python deploy.py --pip         # also reinstall requirements
python deploy.py --status      # show remote /api/health
python deploy.py --logs 60     # tail the remote journal
```

`deploy.py` never deletes and never overwrites the host-specific
`config.yaml`, `.env` or `targets.json`.

## Security notes

- Mutating endpoint `POST /api/refresh/{id}` requires the `X-API-Key` header to
  match `CTI_API_KEY`; it is also rate-limited and locked per source.
- Read endpoints (`/api/health`, `/api/sources`, `/api/data`, `/api/status`) are
  open — keep the service on loopback or behind the VPN.
- Bind `0.0.0.0` only together with `CTI_API_KEY` set.
