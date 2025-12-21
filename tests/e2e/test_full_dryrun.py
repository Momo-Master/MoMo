from __future__ import annotations

import http.client
import socket
import subprocess
import time
from pathlib import Path


def _get_free_port() -> int:
    """Get a free port by binding to port 0 and letting the OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


import pytest


@pytest.mark.skip(reason="Flaky on Windows - port binding race condition")
def test_full_dryrun_metrics(tmp_path: Path):
    # Get dynamic ports to avoid CI conflicts
    health_port = _get_free_port()
    prom_port = _get_free_port()
    web_port = _get_free_port()
    
    # Create config with dynamic web port
    cfg_path = tmp_path / "momo.yml"
    cfg_text = Path("configs/momo.yml").read_text(encoding="utf-8")
    cfg_text = cfg_text.replace("bind_port: 8082", f"bind_port: {web_port}")
    cfg_path.write_text(cfg_text, encoding="utf-8")
    
    # Start core in dry-run with dynamic ports
    proc = subprocess.Popen([
        "python", "-m", "momo.cli", "run", "-c", str(cfg_path), "--dry-run",
        "--health-port", str(health_port), "--prom-port", str(prom_port),
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(2)

        ok = False
        t0 = time.time()
        while time.time() - t0 < 15:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", prom_port, timeout=2)
                conn.request("GET", "/metrics")
                r = conn.getresponse()
                data = r.read().decode()
                if "momo_plugins_enabled" in data and "momo_rotations_total" in data:
                    ok = True
                    break
            except Exception:
                time.sleep(0.5)
        assert ok, f"Metrics endpoint http://127.0.0.1:{prom_port}/metrics did not respond correctly"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


