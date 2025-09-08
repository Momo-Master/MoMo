# Plugins

MoMo uses a manual “drop‑in” plugin model. A plugin is a Python module under `momo/apps/momo_plugins/` that may expose:

- `init(cfg: MomoConfig) -> None` — called on startup
- `shutdown() -> None` — called on shutdown

Enable plugins in `configs/momo.yml`:

```yaml
plugins:
  enabled: ["autobackup", "wpa-sec"]
  options:
    autobackup: {}
    wpa-sec: {}
```

Guidelines:
- Keep network operations safe; default to dry‑run without credentials.
- Read secrets via environment variables; do not hardcode in YAML.
- Emit Prometheus metrics with `momo_<plugin>_*` names.

AutoBackup specifics:
- Ensure destination directory exists (create if missing).
- On `PermissionError`, log a warning and disable itself gracefully without crashing the core.

