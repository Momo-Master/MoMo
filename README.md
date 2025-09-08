# MoMo

Modular, Pi 5 optimized fork of Pwnagotchi with secure defaults and clean architecture.

## Highlights

- Safe-by-default (passive) runtime with strict guardrails for semi/aggressive
- Robust logging and rotation with storage quotas (default 30 days / 5 GB)
- Manual, drop‑in plugin model (AutoBackup, WPA‑Sec, WebCfg adapter)
- Health and Prometheus metrics endpoints
- Minimal Web UI (token-protected). First boot binds on LAN (0.0.0.0) with a strong token.
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
curl -fsSL https://raw.githubusercontent.com/Project-MoMo/MoMo/main/deploy/momo-quickstart.sh | sudo bash
```

After install, MoMo should be running immediately. You can also run the guided setup to apply/update config and systemd:

```bash
sudo momo wizard --apply
```

Enable selected features during quickstart (optional):

```bash
curl -fsSL https://raw.githubusercontent.com/Project-MoMo/MoMo/main/deploy/momo-quickstart.sh \
  | sudo ENABLE_WEB=1 ENABLE_BETTERCAP=1 bash
```

Then verify services:

```bash
curl 127.0.0.1:8081/healthz
curl 127.0.0.1:9091/metrics
```

## Web UI (one-shot enabled)

- On first boot, Web UI is enabled and bound to `0.0.0.0:8082` with a strong token generated at `/opt/momo/.momo_ui_token`.
- Print URLs and token:

  ```bash
  momo web-url --show-token
  ```

- Access example:

  ```bash
  curl -H "Authorization: Bearer $(cat /opt/momo/.momo_ui_token)" http://<pi-ip>:8082/api/status
  ```

- To rotate the token:

  ```bash
  sudo ROTATE_TOKEN=1 bash /opt/momo/deploy/install.sh
  # or edit /etc/systemd/system/momo.service.d/env.conf and restart
  sudo systemctl daemon-reload && sudo systemctl restart momo
  ```

- Prefer localhost-only? Change `server.web.bind_host` to `127.0.0.1` in `/etc/momo/momo.yml` (or `/opt/momo/configs/momo.yml`), then restart `momo`.

Endpoints: `/api/health`, `/api/status`, `/api/rotate`, `/api/handshakes`, `/api/handshakes/<file>`, `/api/metrics`.

After install (examples):

```bash
curl http://127.0.0.1:8081/healthz
curl http://127.0.0.1:9091/metrics
momo doctor   # shows URLs and token info
```

## Repository Layout

- `momo/`: Python package, core, tools, CLI
- `momo/apps/web/`: minimal static Web UI (HTML/CSS/JS)
- `configs/`: default `momo.yml` and wordlists notes
- `deploy/`: install scripts and systemd units
- `deploy/momo-quickstart.sh`: one-shot installer (curl | bash)
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
- `ENABLE_WEB=0|1`: disable/enable Web UI service (defaults to 1)
- `ENABLE_ACTIVE_WIFI=0|1`: install mdk4/aireplay-ng and enable active_wifi plugin
- `ENABLE_BETTERCAP=0|1`: install bettercap and enable plugin support
- `ENABLE_CRACKING=0|1`: install hashcat/john and enable cracking plugin
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
    # See docs for optional plugins (active_wifi, bettercap, cracker)

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

- Health: `GET /healthz` → basic JSON (default bind `0.0.0.0:8081`)
- Metrics: `GET /metrics` → Prometheus text exposition (default bind `0.0.0.0:9091`)
- Metrics-lite: `GET /api/metrics-lite` → compact JSON for minimal Web UI
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
- Web UI: token is generated at `/opt/momo/.momo_ui_token` on first boot. Use `momo web-url --show-token`.

## Feature Guides

- Active Wi‑Fi (mdk4/aireplay): see `docs/ACTIVE_WIFI.md`
- Bettercap integration: see `docs/BETTERCAP.md`
- Minimal Web UI: see `docs/WEBUI.md`
- Offline cracking: see `docs/CRACKING.md`
- Plugins drop-in & priority: see `docs/PLUGINS.md`

## Security

See `docs/SECURITY.md` for hardening guidance (tokens, binds, UFW/Fail2ban, secrets via systemd drop-ins, aggressive-mode guardrails). By default, a strong token is generated and stored in a systemd drop-in for the Web UI.

## License

MIT — see `LICENSE`.
