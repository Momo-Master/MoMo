# MoMo

Modular, Pi 5 optimized fork of Pwnagotchi with secure defaults and clean architecture.

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

## Web UI (optional)

- Disabled by default; binds to `127.0.0.1:8082` when enabled.
- Set `MOMO_UI_TOKEN` (or `MOMO_UI_PASSWORD`) and enable via installer: `ENABLE_WEB=1`.
- Access: `curl -H "Authorization: Bearer $MOMO_UI_TOKEN" http://127.0.0.1:8082/api/status`
- For LAN access, put a reverse proxy in front (Nginx/Caddy) and keep MoMo bound to localhost.

```bash
curl localhost:8081/healthz
curl localhost:9091/metrics
```

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
