# Cracking Plugin (hashcat/john)

WARNING: Only crack handshakes you obtained legally and ethically.

## Overview

- Linux-only execution. Dry-run/Windows simulates attempts and metrics.
- Watches `logs/*/handshakes/*.22000`, runs selected engine for a limited runtime.
- Writes potfile to `logs/meta/hashcat.potfile` and cracked results under `logs/cracked/`.

## Config

```yaml
plugins:
  enabled: ["cracker"]
  options:
    cracker:
      enabled: true
      engine: hashcat   # or john
      wordlists: ["configs/wordlists/rockyou.txt"]
      rules: []
      max_runtime_secs: 900
      nice: 10
      gpu: false
```

## Metrics

- `momo_cracks_total`, `momo_crack_failures_total`
- `momo_crack_queue_size`

## CLI

- Future: `momo cracks list|tail|run-once`

## Installer

- `ENABLE_CRACKING=1` installs `hashcat` and `john`.
