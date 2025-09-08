# Plugins

## Drop-in model

Place plugin modules under `momo/apps/momo_plugins/` and enable by name in `plugins.enabled`.

## Priority and lifecycle

- Each plugin may define `priority` (default 100). Lower priority loads earlier.
- Lifecycle methods: `init(cfg)`, optional `tick(ctx)`, `shutdown()`.
- The registry isolates exceptions per plugin and continues loading others.

## Metrics

- Core exposes generic plugin loading metrics in the future; individual plugins expose their own `get_metrics()` counters.

