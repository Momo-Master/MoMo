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
