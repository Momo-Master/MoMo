# Operations

## Services

- `momo.service`: runs `momo run -c /opt/momo/configs/momo.yml`
- `momo-oled.service`: optional OLED status (placeholder)

## CLI

- `momo version`
- `momo init <path>`
- `momo config-validate <configs/momo.yml>`
- `momo run -c configs/momo.yml [--health-port 8080] [--dry-run]`
- `momo status -c configs/momo.yml`
- `momo diag -c configs/momo.yml`
- `momo rotate-now -c configs/momo.yml`
### Plugin drop-in workflow

- Copy plugin folders from external sources into `momo/apps/momo_plugins/` (or `_examples/` if unused).
- Ensure each plugin exposes `init(opts)` and optional `shutdown()`.

### Plugin usage examples

- Enable in `configs/momo.yml`:
  - `plugins.enabled: ["autobackup", "wpa-sec"]`
  - `plugins.options.autobackup.*` for adapter configuration
  - Optional per-plugin options: `plugins.options.webcfg.port: 8088`, `plugins.options.wpa_sec.endpoint: "..."`, etc.

### WPA-Sec (opt-in)

- Add `"wpa-sec"` to `plugins.enabled`
- DO NOT put API keys in YAML. Use systemd env overrides:
  - `sudo systemctl edit momo` then:
    - `Environment="WPA_SEC_API_KEY=xxx"`
- Defaults run in `dry_run` until key is provided

### Mini Web Panel (webcfg)

- Default disabled; binds to `127.0.0.1`
- Requires `MOMO_UI_TOKEN` env unless `allow_unauth=true`
- Metrics: `momo_webcfg_requests_total`, `momo_webcfg_active`

### Handshakes Downloader

- `momo handshakes_dl --dest logs/handshakes --since 7d --src logs`

#### AutoBackup quick start

- Drop the original plugin as `momo/apps/momo_plugins/_thirdparty/autobackup_pwn.py` (keep license header)
- Adapter is `momo/apps/momo_plugins/autobackup.py`
- Enable and configure under `plugins.options.autobackup`

## Logs

- Default under `logs/YYYY-MM-DD/`
- `handshakes/*.pcapng` and `*.22000`
- `meta/` for stats JSON (future)

## Health endpoint

- `/healthz` returns basic JSON: `{mode, channel, hs, files, temp}`
- Enabled with `--health-port`

## Prometheus metrics

- `/metrics` exposes Prometheus text format
- Enable with `--prom-port`
- Includes `momo_plugins_enabled` and AutoBackup counters: `momo_autobackup_runs_total`, `momo_autobackup_failures_total`, `momo_autobackup_last_success_timestamp`.

## Rotation

- Automatic based on time/size
- Force rotation: `momo rotate-now -c configs/momo.yml`
- System rotate triggers `SIGUSR1` via logrotate config
