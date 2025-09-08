from __future__ import annotations

import subprocess
import time
from pathlib import Path


def test_full_dryrun_metrics(tmp_path: Path):
    # Start core in dry-run with default config; give servers time to start
    proc = subprocess.Popen([
        "python", "-m", "momo.cli", "run", "-c", "configs/momo.yml", "--dry-run",
        "--health-port", "8081", "--prom-port", "9091",
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(2)
        import http.client

        ok = False
        t0 = time.time()
        while time.time() - t0 < 10:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", 9091, timeout=1)
                conn.request("GET", "/metrics")
                r = conn.getresponse()
                data = r.read().decode()
                if "momo_plugins_enabled" in data and "momo_rotations_total" in data:
                    ok = True
                    break
            except Exception:
                time.sleep(0.5)
        assert ok
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


