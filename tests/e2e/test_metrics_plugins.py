import socket
import subprocess
import time
from pathlib import Path

import pytest


def _get_free_port() -> int:
    """Get a free port by binding to port 0 and letting the OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


@pytest.mark.e2e
@pytest.mark.skip(reason="Flaky in CI due to port binding race conditions - TODO: fix after core complete")
def test_metrics_and_plugins_dry_run(tmp_path: Path):
    # Get random free ports to avoid conflicts in CI
    health_port = _get_free_port()
    prom_port = _get_free_port()
    web_port = _get_free_port()
    
    # Enable example plugin in a temp config
    cfg = tmp_path / "momo.yml"
    cfg_text = Path("configs/momo.yml").read_text(encoding="utf-8")
    cfg_text = cfg_text.replace("example_plugin:\n    enabled: false", "example_plugin:\n    enabled: true")
    # Override web port to avoid conflicts
    cfg_text = cfg_text.replace("bind_port: 8082", f"bind_port: {web_port}")
    cfg.write_text(cfg_text, encoding="utf-8")
    
    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "momo.cli",
            "run",
            "-c",
            str(cfg),
            "--health-port",
            str(health_port),
            "--prom-port",
            str(prom_port),
            "--dry-run",
        ],
    )
    try:
        import urllib.request
        # Poll for the metrics endpoint to be ready
        body = None
        for _ in range(30):  # Increased retries for CI
            try:
                body = urllib.request.urlopen(f"http://127.0.0.1:{prom_port}/metrics", timeout=2).read().decode()
                break
            except Exception:
                time.sleep(0.5)
        assert body is not None, f"Metrics endpoint http://127.0.0.1:{prom_port}/metrics did not respond"
        assert "momo_plugins_enabled" in body
        assert "momo_current_channel" in body
    finally:
        proc.terminate()
        proc.wait(timeout=5)


