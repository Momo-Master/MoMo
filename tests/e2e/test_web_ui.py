import http.client
import socket
import threading
import time

from momo.apps.momo_web import create_app
from momo.config import load_config


def _get_free_port() -> int:
    """Get a free port by binding to port 0 and letting the OS assign one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


def _run_app(app, port):
    app.run(host="127.0.0.1", port=port)


def test_web_ui_auth_and_endpoints(tmp_path, monkeypatch):
    # Get dynamic port to avoid CI conflicts
    web_port = _get_free_port()
    
    # prepare config
    cfg_path = tmp_path / "momo.yml"
    cfg_path.write_text(
        f"""
logging:
  base_dir: "logs"
web:
  enabled: true
  bind_host: 127.0.0.1
  bind_port: {web_port}
  auth:
    token_env: MOMO_UI_TOKEN
    password_env: MOMO_UI_PASSWORD
""",
        encoding="utf-8",
    )
    tmp_logs = tmp_path / "logs"
    (tmp_logs / "meta").mkdir(parents=True, exist_ok=True)
    (tmp_logs / "meta" / "stats.json").write_text("{}", encoding="utf-8")

    cfg = load_config(cfg_path)
    app = create_app(cfg)

    t = threading.Thread(target=_run_app, args=(app, web_port), daemon=True)
    t.start()
    time.sleep(1.5)  # Give Flask time to start

    conn = http.client.HTTPConnection("127.0.0.1", web_port, timeout=2)
    # no auth -> 401 on /api/status
    conn.request("GET", "/api/status")
    r = conn.getresponse()
    assert r.status == 401
    r.read()

    # token auth
    monkeypatch.setenv("MOMO_UI_TOKEN", "secret")
    conn.request("GET", "/api/status", headers={"Authorization": "Bearer secret"})
    r = conn.getresponse()
    assert r.status == 200
    r.read()

    # metrics proxy should return 502 in tests (server not running), but reachable
    conn.request("GET", "/api/metrics")
    r = conn.getresponse()
    assert r.status in (200, 502)
    r.read()


