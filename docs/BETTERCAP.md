# Bettercap Plugin

WARNING: Exposes a local REST API. Bind carefully and prefer token protections.

## Overview

- Linux-only; dry-run/Windows simulates metrics.
- Generates a session file under `logs/meta/bettercap.session` with configured modules.
- Starts `bettercap` headless with REST API on configured address/port.

## Config (plugins.options.bettercap)

```yaml
plugins:
  enabled: ["bettercap"]
  options:
    bettercap:
      enabled: true
      iface: wlan1
      http_ui_port: 8083
      bind_host: 0.0.0.0
      modules: ["wifi.recon on", "events.stream on"]
      extra_args: []
```

## Metrics

- `momo_bettercap_runs_total`, `momo_bettercap_failures_total`
- `momo_bettercap_events_total`
- `momo_bettercap_ui_port`, `momo_bettercap_active`

## Security

- Prefer local binds and reverse proxy/SSH tunneling.
- Ensure firewall (UFW) rules are in place when publicly bound.
