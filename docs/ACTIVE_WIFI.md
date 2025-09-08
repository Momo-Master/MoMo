# Active Wi‑Fi Plugin (mdk4/aireplay)

WARNING: Deauthentication and beacon flooding may be illegal in your jurisdiction. Use only on networks you own or have explicit permission to test.

## Overview

- Linux only; requires `aggressive.enabled: true` and `plugins.options.active_wifi.enabled: true`.
- Dry‑run/Windows: never spawns tools; metrics increment only.
- Preferred tool: `mdk4`; fallback: `aireplay-ng`.

## Config

```yaml
plugins:
  enabled: ["active_wifi"]
  options:
    active_wifi:
      enabled: true
      iface: wlan1
      channels: [1,6,11]
      bssid_whitelist: ["AA:BB:CC:DD:EE:FF"]
      deauth_clients: []
      beacon_ssids: ["TestAP1","TestAP2"]
      pkts_per_second: 50
      max_runtime_secs: 15
      cooldown_secs: 10
      tool: auto
```

## Metrics

- `momo_attack_deauth_runs_total`, `momo_attack_deauth_failures_total`
- `momo_attack_beacon_runs_total`, `momo_attack_beacon_failures_total`
- `momo_attack_active`, `momo_attack_last_rc`

## Safety

- Only runs on Linux with `aggressive.enabled: true`.
- Logs the intended commands; secrets are not logged.
