from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path
from flask import Blueprint, current_app, render_template_string, send_from_directory, request, redirect, url_for, Response

from ...config import MomoConfig
from ...tools.handshakes_dl import parse_since

ui_bp = Blueprint("ui", __name__)


def _cfg() -> MomoConfig:
    return current_app.config["MOMO_CONFIG"]


_BASE = """
<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }}</title>
<style>
body{font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;background:#f7fafc;color:#111827;margin:0}
header,footer{background:#fff;border-bottom:1px solid #e5e7eb;padding:10px 16px}
main{padding:16px;max-width:1100px;margin:0 auto}
h1,h2{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
.nav a{color:#2563eb;text-decoration:none;margin-right:12px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:6px;padding:12px;margin-bottom:12px}
.badge{display:inline-block;background:#e5e7eb;border-radius:999px;padding:2px 8px;font-size:12px;margin-right:6px}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left}
.warn{color:#b91c1c}
</style>
</head><body>
<header><div class="nav"><strong>{{ title }}</strong> ·
<a href="/">Dashboard</a><a href="/handshakes">Handshakes</a><a href="/config">Config</a>
<a href="{{ metrics_url }}">Metrics</a><a href="{{ health_url }}">Health</a>
</div></header>
<main>
{% block content %}{% endblock %}
</main>
<footer><small>{{ footer }}</small></footer>
</body></html>
"""


@ui_bp.get("/")
def dashboard():
    cfg = _cfg()
    stats = {}
    meta = cfg.meta_dir / "stats.json"
    if meta.exists():
        stats = json.loads(meta.read_text(encoding="utf-8"))
    metrics_url = f"http://{cfg.server.metrics.bind_host}:{cfg.server.metrics.port}/metrics" if cfg.server.metrics.enabled else "#"
    health_url = f"http://{cfg.server.health.bind_host}:{cfg.server.health.port}/healthz" if cfg.server.health.enabled else "#"
    warn = []
    if cfg.web.bind_host == "127.0.0.1":
        warn.append("Local-only bind")
    if cfg.web.allow_query_token:
        warn.append("Query token enabled (unsafe)")
    content = f"""
    <div class='card'>
      <h2>Runtime</h2>
      <div class='badge'>mode: {cfg.mode.value}</div>
      <div class='badge'>channel: {stats.get('channel','-')}</div>
      <div class='badge'>files: {stats.get('files','-')}</div>
      <div class='badge'>bytes: {stats.get('bytes','-')}</div>
      <div class='badge'>last rotate: {stats.get('last_rotate','-')}</div>
    </div>
    <div class='card'>
      <h2>Web</h2>
      <div>UI: http://{cfg.web.bind_host}:{cfg.web.bind_port}/</div>
      <div>Metrics: {metrics_url}</div>
      <div>Health: {health_url}</div>
      {('<div class=\"warn\">' + ', '.join(warn) + '</div>') if warn else ''}
    </div>
    """
    return render_template_string(_BASE, title=cfg.web.title, footer=cfg.web.footer, metrics_url=metrics_url, health_url=health_url, content=content)


@ui_bp.get("/handshakes")
def handshakes():
    cfg = _cfg()
    since = request.args.get("since", "24h")
    page = int(request.args.get("page", "1"))
    per_page = 100
    threshold = time.time() - parse_since(since).total_seconds() if since != "all" else 0
    files = []
    for day in sorted(cfg.logging.base_dir.glob("*/"), reverse=True):
        hand = day / cfg.capture.out_dir_name
        for p in hand.glob("*.pcapng"):
            try:
                st = p.stat()
            except Exception:
                continue
            if threshold and st.st_mtime < threshold:
                continue
            files.append((p, st.st_mtime, st.st_size))
    files.sort(key=lambda t: t[1], reverse=True)
    total = len(files)
    start = (page - 1) * per_page
    page_items = files[start : start + per_page]
    rows = []
    for p, mtime, size in page_items:
        rows.append(f"<tr><td><a href='/download/{p.relative_to(cfg.logging.base_dir)}'>{p.name}</a></td><td>{size}</td><td>{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))}</td></tr>")
    pager = ""
    if total > per_page:
        pager = f"<div>Page {page} — <a href='?since={since}&page={page+1}'>Next</a></div>"
    table = """
    <div class='card'>
      <h2>Handshakes</h2>
      <div><a class='badge' href='?since=24h'>24h</a><a class='badge' href='?since=7d'>7d</a><a class='badge' href='?since=all'>all</a></div>
      <table><thead><tr><th>File</th><th>Size</th><th>Mtime</th></tr></thead><tbody>{rows}</tbody></table>
      <div style='margin-top:8px;'><a class='badge' href='/handshakes/export?since={since}'>Export ZIP</a></div>
      {pager}
    </div>
    """.replace("{rows}", "\n".join(rows)).replace("{since}", since).replace("{pager}", pager)
    metrics_url = f"http://{cfg.server.metrics.bind_host}:{cfg.server.metrics.port}/metrics" if cfg.server.metrics.enabled else "#"
    health_url = f"http://{cfg.server.health.bind_host}:{cfg.server.health.port}/healthz" if cfg.server.health.enabled else "#"
    return render_template_string(_BASE, title=cfg.web.title, footer=cfg.web.footer, metrics_url=metrics_url, health_url=health_url, content=table)


@ui_bp.get("/download/<path:relpath>")
def download(relpath: str):
    cfg = _cfg()
    base = cfg.logging.base_dir
    p = (base / relpath).resolve()
    if not str(p).startswith(str(base.resolve())):
        return Response(status=404)
    if not p.exists():
        return Response(status=404)
    return send_from_directory(base, relpath, as_attachment=True)


@ui_bp.post("/delete/<path:relpath>")
def delete(relpath: str):
    cfg = _cfg()
    if not cfg.web.allow_delete:
        return Response(status=403)
    base = cfg.logging.base_dir
    p = (base / relpath).resolve()
    if not str(p).startswith(str(base.resolve())) or not p.exists():
        return Response(status=404)
    try:
        p.unlink()
    except Exception:
        return Response(status=500)
    return redirect(url_for("ui.handshakes"))


@ui_bp.get("/handshakes/export")
def export_zip():
    cfg = _cfg()
    since = request.args.get("since", "24h")
    threshold = time.time() - parse_since(since).total_seconds() if since != "all" else 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for day in sorted(cfg.logging.base_dir.glob("*/"), reverse=True):
            hand = day / cfg.capture.out_dir_name
            for p in hand.glob("*.pcapng"):
                try:
                    st = p.stat()
                except Exception:
                    continue
                if threshold and st.st_mtime < threshold:
                    continue
                zf.write(p, arcname=p.name)
    buf.seek(0)
    ts = time.strftime("%Y%m%d-%H%M")
    return Response(buf.getvalue(), headers={"Content-Disposition": f"attachment; filename=momo-handshakes-{ts}.zip"}, mimetype="application/zip")


@ui_bp.get("/config")
def config_page():
    cfg = _cfg()
    raw = Path.resolve(Path("/dev/null"))  # placeholder to avoid exposing envs; we show file text
    text = ""
    try:
        text = Path(cfg_path := str(current_app.config.get("MOMO_CONFIG_PATH", ""))).read_text(encoding="utf-8") if cfg_path else ""
    except Exception:
        pass
    code = f"<div class='card'><h2>Config</h2><pre>{(text or '').replace('<','&lt;')}</pre></div>"
    metrics_url = f"http://{cfg.server.metrics.bind_host}:{cfg.server.metrics.port}/metrics" if cfg.server.metrics.enabled else "#"
    health_url = f"http://{cfg.server.health.bind_host}:{cfg.server.health.port}/healthz" if cfg.server.health.enabled else "#"
    return render_template_string(_BASE, title=cfg.web.title, footer=cfg.web.footer, metrics_url=metrics_url, health_url=health_url, content=code)


