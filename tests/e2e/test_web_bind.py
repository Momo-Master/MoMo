from __future__ import annotations

import http.client
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def _get_free_port() -> int:
    """Get a free port by binding to port 0 and letting the OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


def test_metrics_lite_dryrun():
    # Get dynamic ports to avoid CI conflicts
    health_port = _get_free_port()
    prom_port = _get_free_port()
    web_port = _get_free_port()
    
    # Create config with dynamic web port
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "momo.yml"
        cfg_text = Path("configs/momo.yml").read_text(encoding="utf-8")
        cfg_text = cfg_text.replace("bind_port: 8082", f"bind_port: {web_port}")
        cfg_path.write_text(cfg_text, encoding="utf-8")
        
        env = os.environ.copy()
        env["MOMO_UI_TOKEN"] = ""
        proc = subprocess.Popen([
            "python", "-m", "momo.cli", "run", "-c", str(cfg_path), "--dry-run",
            "--health-port", str(health_port), "--prom-port", str(prom_port),
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        try:
            ok = False
            t0 = time.time()
            while time.time() - t0 < 15:
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", web_port, timeout=2)
                    conn.request("GET", "/api/metrics-lite")
                    r = conn.getresponse()
                    if r.status in (200, 401, 403, 502):
                        # accept 200 (no token) or 401 if token required in env
                        if r.status == 200:
                            ok = True
                            break
                    r.read()
                except Exception:
                    time.sleep(0.5)
            assert ok, f"Metrics-lite endpoint http://127.0.0.1:{web_port}/api/metrics-lite did not respond with 200"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()


