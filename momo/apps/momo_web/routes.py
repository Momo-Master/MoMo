from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    current_app,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)

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
<a href="/">Dashboard</a><a href="/handshakes">Handshakes</a><a href="/map">Map</a><a href="/config">Config</a>
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
      {('<div class="warn">' + ', '.join(warn) + '</div>') if warn else ''}
    </div>
    """
    return render_template_string(_BASE, title=cfg.web.title, footer=cfg.web.footer, metrics_url=metrics_url, health_url=health_url, content=content)


@ui_bp.get("/handshakes")
def handshakes():
    cfg = _cfg()
    since = request.args.get("since", "24h")
    # SECURITY: Validate and limit page number
    try:
        page = max(1, min(int(request.args.get("page", "1")), 1000))
    except (ValueError, TypeError):
        page = 1
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
    Path.resolve(Path("/dev/null"))  # placeholder to avoid exposing envs; we show file text
    text = ""
    try:
        cfg_path = str(current_app.config.get("MOMO_CONFIG_PATH", ""))
        text = Path(cfg_path).read_text(encoding="utf-8") if cfg_path else ""
    except Exception:
        pass
    code = f"<div class='card'><h2>Config</h2><pre>{(text or '').replace('<','&lt;')}</pre></div>"
    metrics_url = f"http://{cfg.server.metrics.bind_host}:{cfg.server.metrics.port}/metrics" if cfg.server.metrics.enabled else "#"
    health_url = f"http://{cfg.server.health.bind_host}:{cfg.server.health.port}/healthz" if cfg.server.health.enabled else "#"
    return render_template_string(_BASE, title=cfg.web.title, footer=cfg.web.footer, metrics_url=metrics_url, health_url=health_url, content=code)


_MAP_PAGE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }} - Wardriving Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: ui-sans-serif, system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
        header { background: #1e293b; padding: 12px 20px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
        header h1 { font-size: 18px; font-weight: 600; color: #22d3ee; }
        .nav a { color: #94a3b8; text-decoration: none; margin-left: 16px; font-size: 14px; }
        .nav a:hover { color: #22d3ee; }
        #map { height: calc(100vh - 120px); width: 100%; }
        .stats-bar { background: #1e293b; padding: 10px 20px; display: flex; gap: 24px; border-top: 1px solid #334155; }
        .stat { display: flex; flex-direction: column; }
        .stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; }
        .stat-value { font-size: 18px; font-weight: 600; color: #22d3ee; }
        .legend { position: absolute; bottom: 80px; right: 20px; background: #1e293b; padding: 12px; border-radius: 8px; z-index: 1000; border: 1px solid #334155; }
        .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; }
        .legend-dot { width: 12px; height: 12px; border-radius: 50%; }
        .popup-content { font-size: 13px; }
        .popup-content strong { color: #0f172a; }
        .popup-ssid { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
        .popup-bssid { font-family: monospace; color: #64748b; font-size: 11px; }
        .live-indicator { display: flex; align-items: center; gap: 6px; }
        .live-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <header>
        <h1>🗺️ MoMo Wardriving Map</h1>
        <div class="nav">
            <span class="live-indicator"><span class="live-dot"></span> Live</span>
            <a href="/">Dashboard</a>
            <a href="/handshakes">Handshakes</a>
            <a href="/config">Config</a>
        </div>
    </header>
    
    <div id="map"></div>
    
    <div class="stats-bar">
        <div class="stat">
            <span class="stat-label">Total APs</span>
            <span class="stat-value" id="stat-total">-</span>
        </div>
        <div class="stat">
            <span class="stat-label">With GPS</span>
            <span class="stat-value" id="stat-gps">-</span>
        </div>
        <div class="stat">
            <span class="stat-label">Handshakes</span>
            <span class="stat-value" id="stat-hs">-</span>
        </div>
        <div class="stat">
            <span class="stat-label">Cracked</span>
            <span class="stat-value" id="stat-cracked">-</span>
        </div>
        <div class="stat">
            <span class="stat-label">Distance</span>
            <span class="stat-value" id="stat-distance">-</span>
        </div>
        <div class="stat">
            <span class="stat-label">GPS Fix</span>
            <span class="stat-value" id="stat-fix">-</span>
        </div>
    </div>
    
    <div class="legend">
        <div class="legend-item"><span class="legend-dot" style="background:#22c55e"></span> WPA2/WPA3</div>
        <div class="legend-item"><span class="legend-dot" style="background:#eab308"></span> WPA</div>
        <div class="legend-item"><span class="legend-dot" style="background:#f97316"></span> WEP</div>
        <div class="legend-item"><span class="legend-dot" style="background:#ef4444"></span> Open</div>
        <div class="legend-item"><span class="legend-dot" style="background:#3b82f6"></span> Handshake</div>
        <div class="legend-item"><span class="legend-dot" style="background:#8b5cf6"></span> Cracked</div>
    </div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script>
        // Initialize map
        const map = L.map('map').setView([41.0082, 28.9784], 13);  // Default: Istanbul
        
        // Dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);
        
        // Layer groups
        const apLayer = L.layerGroup().addTo(map);
        let apMarkers = {};
        
        // Load APs from API
        async function loadAPs() {
            try {
                const resp = await fetch('/api/wardriver/aps?limit=5000');
                const data = await resp.json();
                
                if (data.features && data.features.length > 0) {
                    // Clear old markers
                    apLayer.clearLayers();
                    apMarkers = {};
                    
                    // Bounds for auto-fit
                    const bounds = L.latLngBounds();
                    
                    data.features.forEach(feature => {
                        const coords = feature.geometry.coordinates;
                        const props = feature.properties;
                        const lat = coords[1];
                        const lon = coords[0];
                        
                        bounds.extend([lat, lon]);
                        
                        // Create circle marker
                        const marker = L.circleMarker([lat, lon], {
                            radius: 8,
                            fillColor: props.color,
                            color: '#1e293b',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.8
                        });
                        
                        // Popup content
                        const popup = `
                            <div class="popup-content">
                                <div class="popup-ssid">${escapeHtml(props.ssid)}</div>
                                <div class="popup-bssid">${props.bssid}</div>
                                <hr style="margin: 6px 0; border-color: #e5e7eb;">
                                <div><strong>Channel:</strong> ${props.channel}</div>
                                <div><strong>Signal:</strong> ${props.rssi} dBm</div>
                                <div><strong>Encryption:</strong> ${props.encryption.toUpperCase()}</div>
                                ${props.handshake ? '<div style="color:#3b82f6">✓ Handshake captured</div>' : ''}
                                ${props.cracked ? '<div style="color:#8b5cf6">✓ Password cracked</div>' : ''}
                            </div>
                        `;
                        
                        marker.bindPopup(popup);
                        marker.addTo(apLayer);
                        apMarkers[props.bssid] = marker;
                    });
                    
                    // Update stats
                    document.getElementById('stat-gps').textContent = data.features.length;
                    
                    // Fit map to bounds
                    if (bounds.isValid()) {
                        map.fitBounds(bounds, { padding: [50, 50] });
                    }
                }
            } catch (err) {
                console.error('Failed to load APs:', err);
            }
        }
        
        // Load plugin stats
        async function loadStats() {
            try {
                const resp = await fetch('/api/wardriver/status');
                const data = await resp.json();
                
                if (data.stats) {
                    document.getElementById('stat-total').textContent = data.stats.aps_total || 0;
                    document.getElementById('stat-hs').textContent = data.stats.aps_new_session || 0;
                    document.getElementById('stat-distance').textContent = 
                        (data.stats.distance_km || 0).toFixed(2) + ' km';
                    document.getElementById('stat-fix').textContent = 
                        data.stats.gps_fix ? '✓ Yes' : '✗ No';
                }
            } catch (err) {
                console.error('Failed to load stats:', err);
            }
        }
        
        // SSE for real-time updates
        function connectSSE() {
            const evtSource = new EventSource('/sse/events');
            
            evtSource.onmessage = (e) => {
                try {
                    const event = JSON.parse(e.data);
                    
                    if (event.type === 'AP_DISCOVERED' || event.type === 'AP_UPDATED') {
                        // Could update individual marker here
                        // For now, just reload periodically
                    }
                    
                    if (event.type === 'GPS_POSITION_UPDATE') {
                        // Could show current position
                    }
                    
                    if (event.type === 'SCAN_COMPLETED') {
                        loadStats();
                    }
                } catch (err) {
                    console.error('SSE parse error:', err);
                }
            };
            
            evtSource.onerror = () => {
                evtSource.close();
                setTimeout(connectSSE, 5000);
            };
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }
        
        // Initial load
        loadAPs();
        loadStats();
        connectSSE();
        
        // Refresh every 30 seconds
        setInterval(loadAPs, 30000);
        setInterval(loadStats, 10000);
    </script>
</body>
</html>
"""


@ui_bp.get("/map")
def map_page():
    """Wardriving map page with Leaflet.js."""
    cfg = _cfg()
    return render_template_string(_MAP_PAGE, title=cfg.web.title)


