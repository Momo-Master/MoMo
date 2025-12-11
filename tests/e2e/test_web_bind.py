from __future__ import annotations

import http.client
import os
import subprocess
import time


def test_metrics_lite_dryrun():
    env = os.environ.copy()
    env["MOMO_UI_TOKEN"] = ""
    proc = subprocess.Popen([
        "python", "-m", "momo.cli", "run", "-c", "configs/momo.yml", "--dry-run",
        "--health-port", "8081", "--prom-port", "9091",
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    try:
        ok = False
        t0 = time.time()
        while time.time() - t0 < 10:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", 8082, timeout=1)
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
        assert ok
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


