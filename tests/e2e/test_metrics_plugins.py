import subprocess
import time
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_metrics_and_plugins_dry_run(tmp_path: Path):
    # Enable example plugin in a temp config
    cfg = tmp_path / "momo.yml"
    cfg.write_text(
        (
            Path("configs/momo.yml").read_text(encoding="utf-8")
            .replace("example_plugin:\n    enabled: false", "example_plugin:\n    enabled: true")
        ),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "momo.cli",
            "run",
            "-c",
            str(cfg),
            "--health-port",
            "8081",
            "--prom-port",
            "9091",
            "--dry-run",
        ]
    )
    try:
        time.sleep(1.0)
        # Fetch metrics
        import urllib.request

        body = urllib.request.urlopen("http://127.0.0.1:9091/metrics").read().decode()
        assert "momo_plugins_enabled" in body
        assert "momo_current_channel" in body
    finally:
        proc.terminate()
        proc.wait(timeout=5)


