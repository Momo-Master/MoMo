# MoMo

Modular, Pi 5 optimized fork of Pwnagotchi with secure defaults and clean architecture.

## Highlights

- Safe-by-default (passive) runtime with strict guardrails for semi/aggressive
- Robust logging and rotation with storage quotas (default 30 days / 5 GB)
- Manual, drop‑in plugin model (AutoBackup, WPA‑Sec, WebCfg adapter)
- Health and Prometheus metrics endpoints
- Optional Web UI (localhost only by default, token/basic auth)
- One‑shot quickstart script and unified, idempotent installer
- First‑boot finalization and image build scaffolding (pi‑gen)

## Quickstart (Dev)

```bash
python -m pip install --upgrade pip
pip install -e .[dev]
pre-commit install
momo version
momo config-validate configs/momo.yml
```

## Quick Start (Raspberry Pi 5 / Bookworm)

Run as root on a fresh Pi 5 Bookworm image:

```bash
curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/deploy/momo-quickstart.sh | bash
```

Then reboot and verify services:

```bash
curl localhost:8081/healthz
curl localhost:9091/metrics
```

## Web UI (optional)

- Disabled by default; binds to `127.0.0.1:8082` when enabled.
- Set `MOMO_UI_TOKEN` (or `MOMO_UI_PASSWORD`) and enable via installer: `ENABLE_WEB=1`.
- Access: `curl -H "Authorization: Bearer $MOMO_UI_TOKEN" http://127.0.0.1:8082/api/status`
- For LAN access, put a reverse proxy in front (Nginx/Caddy) and keep MoMo bound to localhost.

Endpoints: `/api/health`, `/api/status`, `/api/rotate`, `/api/handshakes`, `/api/handshakes/<file>`, `/api/metrics`.

## Repository Layout

- `momo/`: Python package, core, tools, CLI
- `configs/`: default `momo.yml` and wordlists notes
- `deploy/`: install scripts and systemd units
- `docs/`: setup, operations, security
- `tests/`: unit and e2e tests

## Goals
- Secure-by-default
- Rotating logs and clean configs
- Optional OLED UI
- Passive mode by default, safe flags for aggressive actions

See `docs/` for detailed guidance.

## Installation (Unified Installer)

The quickstart fetches and runs the unified installer (`deploy/install.sh`). You can also run it manually:

```bash
sudo NONINTERACTIVE=1 ENABLE_WEB=0 ENABLE_OLED=0 ENABLE_SECURITY=0 \
  MOMO_IFACE=wlan1 MOMO_REG=TR \
  bash deploy/install.sh
```

- Installs MoMo under `/opt/momo` with a virtualenv at `/opt/momo/.venv`.
- Installs systemd units: `momo.service` (and optional `momo-web.service`, `momo-oled.service`).
- If the USB adapter `2357:0120` is detected, attempts DKMS driver install (skip with `SKIP_DKMS=1`).
- Idempotent: safe to re‑run (upgrades app, preserves config).

Flags (env):
- `NONINTERACTIVE=1`: do not prompt
- `MOMO_IFACE=wlan1`: interface name
- `MOMO_REG=TR`: regulatory domain
- `ENABLE_WEB=1`: enable Web UI service
- `ENABLE_OLED=1`: enable OLED service (placeholder)
- `ENABLE_SECURITY=1`: apply UFW+fail2ban baseline
- `NO_START=1`: install but do not start services

## Services (systemd)

```bash
sudo systemctl status momo
sudo journalctl -u momo -f
```

Optional:
- `momo-web.service` (Web UI) — enable via `ENABLE_WEB=1`
- `momo-oled.service` (placeholder)

## Configuration

Edit `configs/momo.yml`. Key sections:

```yaml
interface:
  name: wlan1
  regulatory_domain: TR

capture:
  enable_on_windows: false
  simulate_bytes_per_file: 16384
  simulate_dwell_secs: 2
  naming:
    by_ssid: true
    template: "{ts}__{ssid}__{bssid}__ch{channel}"
    max_name_len: 64
    allow_unicode: false
    whitespace: "_"

web:
  enabled: false
  bind_host: 127.0.0.1
  bind_port: 8082
  auth:
    token_env: MOMO_UI_TOKEN
    password_env: MOMO_UI_PASSWORD
  rate_limit: "60/minute"

plugins:
  enabled: ["autobackup", "wpa-sec"]
  options:
    autobackup: {}
    wpa-sec: {}

storage:
  enabled: true
  max_days: 30
  max_gb: 5.0
  low_space_gb: 1.0
```

Notes:
- SSID‑based renaming applies after rotation; hidden/empty SSIDs fall back safely; collisions get `__2`, `__3` suffixes.
- Storage quotas prune by day and total size with metrics.
- Plugins follow a manual drop‑in model: copy modules under `momo/apps/momo_plugins/` and enable in config.

## CLI

```bash
momo version
momo config-validate configs/momo.yml
momo run -c configs/momo.yml --health-port 8081 --prom-port 9091
momo status -c configs/momo.yml
momo diag -c configs/momo.yml
momo rotate-now -c configs/momo.yml
```

## Health and Metrics

- Health: `GET /healthz` → basic JSON
- Metrics: `GET /metrics` → Prometheus text exposition
- Example metrics: `momo_rotations_total`, `momo_handshakes_total`, `momo_convert_skipped_total`,
  `momo_rename_total`, `momo_rename_skipped_total`, `momo_last_ssid_present`, storage quota gauges

## Image Build (pi‑gen)

Scaffolded wrapper and stage are under `deploy/image/`:

```bash
bash deploy/image/make_image.sh
```

Outputs are placed by pi‑gen under `pi-gen/deploy/`. Use `rpi-imager` or `dd` to flash.

## Troubleshooting (quick hints)

- Adapter driver: set `SKIP_DKMS=1` if building kernel module is not desired in your environment.
- WPA‑Sec: set `WPA_SEC_API_KEY` via systemd overrides; the plugin runs in dry‑run until provided.
- Web UI: ensure `MOMO_UI_TOKEN` or `MOMO_UI_PASSWORD` is set; service binds to localhost by default.

## License

MIT — see `LICENSE`.
