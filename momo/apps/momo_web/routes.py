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
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: #1a1f2e;
            --bg-card-hover: #242b3d;
            --accent-cyan: #22d3ee;
            --accent-green: #10b981;
            --accent-purple: #a78bfa;
            --accent-orange: #f97316;
            --accent-red: #ef4444;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border: #2d3748;
            --glow: rgba(34, 211, 238, 0.15);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Space Grotesk', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            position: fixed;
            left: 0;
            top: 0;
            width: 72px;
            height: 100vh;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 0;
            z-index: 100;
        }
        
        .logo {
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 700;
            color: var(--accent-cyan);
            margin-bottom: 40px;
            text-shadow: 0 0 20px var(--glow);
        }
        
        .nav-item {
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            margin-bottom: 8px;
            color: var(--text-muted);
            text-decoration: none;
            transition: all 0.2s;
            font-size: 20px;
        }
        
        .nav-item:hover, .nav-item.active {
            background: var(--bg-card);
            color: var(--accent-cyan);
            box-shadow: 0 0 20px var(--glow);
        }
        
        .nav-item.active {
            background: linear-gradient(135deg, rgba(34, 211, 238, 0.2), rgba(16, 185, 129, 0.1));
        }
        
        /* Main content */
        .main {
            margin-left: 72px;
            padding: 24px 32px;
            max-width: 1400px;
        }
        
        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 600;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-status {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: var(--bg-card);
            border-radius: 24px;
            font-size: 13px;
            font-weight: 500;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 8px var(--accent-green); }
            50% { opacity: 0.6; box-shadow: none; }
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.3s;
        }
        
        .stat-card:hover {
            background: var(--bg-card-hover);
            border-color: var(--accent-cyan);
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        
        .stat-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            margin-bottom: 16px;
        }
        
        .stat-icon.cyan { background: rgba(34, 211, 238, 0.15); }
        .stat-icon.green { background: rgba(16, 185, 129, 0.15); }
        .stat-icon.purple { background: rgba(167, 139, 250, 0.15); }
        .stat-icon.orange { background: rgba(249, 115, 22, 0.15); }
        
        .stat-label {
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 32px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .stat-change {
            font-size: 12px;
            margin-top: 8px;
        }
        
        .stat-change.positive { color: var(--accent-green); }
        .stat-change.negative { color: var(--accent-red); }
        
        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 18px;
            font-weight: 600;
        }
        
        /* Table */
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            text-align: left;
            padding: 12px 16px;
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }
        
        td {
            padding: 16px;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }
        
        tr:hover td {
            background: var(--bg-card-hover);
        }
        
        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-green));
            color: var(--bg-primary);
        }
        
        .btn-primary:hover {
            box-shadow: 0 4px 20px var(--glow);
            transform: translateY(-1px);
        }
        
        .btn-secondary {
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .btn-secondary:hover {
            border-color: var(--accent-cyan);
        }
        
        /* Badge */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .badge-success { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); }
        .badge-warning { background: rgba(249, 115, 22, 0.15); color: var(--accent-orange); }
        .badge-danger { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); }
        .badge-info { background: rgba(34, 211, 238, 0.15); color: var(--accent-cyan); }
        
        /* Activity Feed */
        .activity-item {
            display: flex;
            align-items: flex-start;
            gap: 16px;
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .activity-item:last-child { border-bottom: none; }
        
        .activity-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-title {
            font-weight: 500;
            margin-bottom: 4px;
        }
        
        .activity-time {
            font-size: 12px;
            color: var(--text-muted);
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .sidebar { width: 60px; }
            .main { margin-left: 60px; padding: 16px; }
            .stats-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <nav class="sidebar">
        <div class="logo">M</div>
        <a href="/" class="nav-item {{ 'active' if active == 'dashboard' else '' }}" title="Dashboard">🏠</a>
        <a href="/handshakes" class="nav-item {{ 'active' if active == 'handshakes' else '' }}" title="Handshakes">🔐</a>
        <a href="/map" class="nav-item {{ 'active' if active == 'map' else '' }}" title="Map">🗺️</a>
        <a href="/captures" class="nav-item {{ 'active' if active == 'captures' else '' }}" title="Captures">📡</a>
        <a href="/bluetooth" class="nav-item {{ 'active' if active == 'bluetooth' else '' }}" title="Bluetooth">📶</a>
        <a href="/eviltwin" class="nav-item {{ 'active' if active == 'eviltwin' else '' }}" title="Evil Twin">👿</a>
        <a href="/config" class="nav-item {{ 'active' if active == 'config' else '' }}" title="Config">⚙️</a>
    </nav>
    
    <main class="main">
        {{ content | safe }}
    </main>
    
    <script>
        // SSE for real-time updates
        function connectSSE() {
            const evtSource = new EventSource('/sse/events');
            evtSource.onmessage = (e) => {
                try {
                    const event = JSON.parse(e.data);
                    console.log('SSE:', event);
                    // Update UI based on event type
                    if (event.type === 'HANDSHAKE_CAPTURED') {
                        location.reload();
                    }
                } catch (err) {}
            };
            evtSource.onerror = () => {
                evtSource.close();
                setTimeout(connectSSE, 5000);
            };
        }
        connectSSE();
    </script>
</body>
</html>
"""


@ui_bp.get("/")
def dashboard():
    cfg = _cfg()
    stats = {}
    meta = cfg.meta_dir / "stats.json"
    if meta.exists():
        try:
            stats = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Count handshakes
    hs_count = 0
    hs_dir = Path(cfg.handshakes_dir) if hasattr(cfg, "handshakes_dir") else cfg.logging.base_dir / "handshakes"
    if hs_dir.exists():
        hs_count = len(list(hs_dir.glob("*.pcapng"))) + len(list(hs_dir.glob("*.22000")))

    # Mode badge color
    mode_class = "badge-success" if cfg.mode.value == "aggressive" else "badge-warning"

    content = f"""
    <div class="header">
        <h1>🔥 MoMo Dashboard</h1>
        <div class="header-status">
            <div class="status-badge">
                <span class="status-dot"></span>
                <span>System Online</span>
            </div>
            <span class="badge {mode_class}">{cfg.mode.value.upper()}</span>
        </div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon cyan">📡</div>
            <div class="stat-label">Access Points</div>
            <div class="stat-value" id="stat-aps">{stats.get('aps_total', 0)}</div>
            <div class="stat-change positive">↑ Live scanning</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon green">🔐</div>
            <div class="stat-label">Handshakes</div>
            <div class="stat-value" id="stat-hs">{hs_count}</div>
            <div class="stat-change">Captured</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon purple">🗺️</div>
            <div class="stat-label">Distance</div>
            <div class="stat-value" id="stat-dist">{stats.get('distance_km', 0):.1f} km</div>
            <div class="stat-change">Traveled</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon orange">🌡️</div>
            <div class="stat-label">Temperature</div>
            <div class="stat-value" id="stat-temp">{stats.get('temp', '--')}°C</div>
            <div class="stat-change">CPU</div>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
        <div class="card">
            <div class="card-header">
                <span class="card-title">📊 System Info</span>
                <a href="/config" class="btn btn-secondary">View Config</a>
            </div>
            <table>
                <tr>
                    <td style="color: var(--text-muted);">Mode</td>
                    <td><span class="badge {mode_class}">{cfg.mode.value}</span></td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Interface</td>
                    <td><code style="color: var(--accent-cyan);">{cfg.interface.name}</code></td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Channels (2.4GHz)</td>
                    <td>{', '.join(map(str, cfg.interface.channels[:6]))}...</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Storage</td>
                    <td>{stats.get('free_gb', '--')} GB free</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Last Rotate</td>
                    <td>{stats.get('last_rotate', 'Never')}</td>
                </tr>
            </table>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span class="card-title">⚡ Quick Actions</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <a href="/map" class="btn btn-primary">🗺️ Open Map</a>
                <a href="/handshakes" class="btn btn-secondary">🔐 View Handshakes</a>
                <a href="/api/captures/stats" class="btn btn-secondary">📊 Capture Stats</a>
                <a href="/api/wardriver/status" class="btn btn-secondary">📡 Wardriver Status</a>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <span class="card-title">📜 Recent Activity</span>
        </div>
        <div class="activity-item">
            <div class="activity-icon" style="background: rgba(34, 211, 238, 0.15);">📡</div>
            <div class="activity-content">
                <div class="activity-title">System Started</div>
                <div class="activity-time">Dashboard loaded • Mode: {cfg.mode.value}</div>
            </div>
        </div>
        <div class="activity-item">
            <div class="activity-icon" style="background: rgba(16, 185, 129, 0.15);">✅</div>
            <div class="activity-content">
                <div class="activity-title">Plugins Loaded</div>
                <div class="activity-time">{len(cfg.plugins.enabled)} plugins active</div>
            </div>
        </div>
        <div class="activity-item">
            <div class="activity-icon" style="background: rgba(167, 139, 250, 0.15);">🔐</div>
            <div class="activity-content">
                <div class="activity-title">Handshake Storage</div>
                <div class="activity-time">{hs_count} files in storage</div>
            </div>
        </div>
    </div>
    """
    return render_template_string(_BASE, title=cfg.web.title, active="dashboard", content=content)


@ui_bp.get("/handshakes")
def handshakes():
    cfg = _cfg()
    since = request.args.get("since", "24h")
    # SECURITY: Validate and limit page number
    try:
        page = max(1, min(int(request.args.get("page", "1")), 1000))
    except (ValueError, TypeError):
        page = 1
    per_page = 50
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

    def format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    rows = []
    for p, mtime, size in page_items:
        time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        rows.append(f"""
        <tr>
            <td>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 20px;">📄</span>
                    <div>
                        <div style="font-weight: 500;">{p.stem[:40]}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">.pcapng</div>
                    </div>
                </div>
            </td>
            <td><span class="badge badge-info">{format_size(size)}</span></td>
            <td style="color: var(--text-secondary);">{time_str}</td>
            <td>
                <a href='/download/{p.relative_to(cfg.logging.base_dir)}' class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;">
                    ⬇️ Download
                </a>
            </td>
        </tr>
        """)

    # Filter buttons
    filter_btns = ""
    for f in [("1h", "1 Hour"), ("24h", "24 Hours"), ("7d", "7 Days"), ("all", "All")]:
        active = "btn-primary" if since == f[0] else "btn-secondary"
        filter_btns += f'<a href="?since={f[0]}" class="btn {active}" style="padding: 8px 16px;">{f[1]}</a>'

    # Pagination
    pager = ""
    if total > per_page:
        pages = (total + per_page - 1) // per_page
        pager = f"""
        <div style="display: flex; justify-content: center; gap: 8px; margin-top: 20px;">
            {'<a href="?since=' + since + '&page=' + str(page-1) + '" class="btn btn-secondary">← Prev</a>' if page > 1 else ''}
            <span class="badge badge-info">Page {page} of {pages}</span>
            {'<a href="?since=' + since + '&page=' + str(page+1) + '" class="btn btn-secondary">Next →</a>' if page < pages else ''}
        </div>
        """

    empty_state = """
    <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
        <div style="font-size: 48px; margin-bottom: 16px;">🔐</div>
        <div style="font-size: 18px; margin-bottom: 8px;">No handshakes captured yet</div>
        <div style="font-size: 14px;">Start scanning to capture WPA handshakes</div>
    </div>
    """ if not rows else ""

    content = f"""
    <div class="header">
        <h1>🔐 Handshakes</h1>
        <div class="header-status">
            <span class="badge badge-success">{total} files</span>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <div style="display: flex; gap: 8px;">
                {filter_btns}
            </div>
            <a href="/handshakes/export?since={since}" class="btn btn-primary">
                📦 Export ZIP
            </a>
        </div>
        
        {empty_state}
        
        {'<table><thead><tr><th>File</th><th>Size</th><th>Modified</th><th>Action</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>' if rows else ''}
        
        {pager}
    </div>
    """
    return render_template_string(_BASE, title=cfg.web.title, active="handshakes", content=content)


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
    text = ""
    try:
        cfg_path = str(current_app.config.get("MOMO_CONFIG_PATH", ""))
        text = Path(cfg_path).read_text(encoding="utf-8") if cfg_path else ""
    except Exception:
        pass

    # Build config sections
    plugins_list = "".join([f'<span class="badge badge-success" style="margin: 2px;">{p}</span>' for p in cfg.plugins.enabled])

    content = f"""
    <div class="header">
        <h1>⚙️ Configuration</h1>
        <div class="header-status">
            <span class="badge badge-info">v0.4.0</span>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
        <div class="card">
            <div class="card-header">
                <span class="card-title">🎯 Mode & Interface</span>
            </div>
            <table>
                <tr>
                    <td style="color: var(--text-muted); width: 40%;">Mode</td>
                    <td><span class="badge badge-success">{cfg.mode.value}</span></td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Interface</td>
                    <td><code style="color: var(--accent-cyan);">{cfg.interface.name}</code></td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">MAC Randomization</td>
                    <td>{'✅ Enabled' if cfg.interface.mac_randomization else '❌ Disabled'}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Channel Hop</td>
                    <td>{'✅ Enabled' if cfg.interface.channel_hop else '❌ Disabled'}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Regulatory</td>
                    <td><code>{cfg.interface.regulatory_domain}</code></td>
                </tr>
            </table>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span class="card-title">🔥 Aggressive Settings</span>
            </div>
            <table>
                <tr>
                    <td style="color: var(--text-muted); width: 40%;">Enabled</td>
                    <td>{'✅ Yes' if cfg.aggressive.enabled else '❌ No'}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Deauth</td>
                    <td>{'✅ Enabled' if cfg.aggressive.deauth.enabled else '❌ Disabled'}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Max Deauth/min</td>
                    <td>{cfg.aggressive.deauth.max_per_minute or 'Unlimited'}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">Evil Twin</td>
                    <td>{'✅ Enabled' if cfg.aggressive.evil_twin.enabled else '❌ Disabled'}</td>
                </tr>
                <tr>
                    <td style="color: var(--text-muted);">PMKID</td>
                    <td>{'✅ Enabled' if cfg.aggressive.pmkid.enabled else '❌ Disabled'}</td>
                </tr>
            </table>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <span class="card-title">🧩 Active Plugins</span>
        </div>
        <div style="padding: 8px 0;">
            {plugins_list}
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <span class="card-title">📄 Raw Config (YAML)</span>
        </div>
        <pre style="background: var(--bg-secondary); padding: 16px; border-radius: 8px; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-secondary); max-height: 400px; overflow-y: auto;">{(text or 'Config file not found').replace('<','&lt;')}</pre>
    </div>
    """
    return render_template_string(_BASE, title=cfg.web.title, active="config", content=content)


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


@ui_bp.get("/captures")
def captures_page():
    """Captures management page."""
    cfg = _cfg()

    content = """
    <div class="header">
        <h1>📡 Capture Manager</h1>
        <div class="header-status">
            <span class="badge badge-info" id="capture-status">Loading...</span>
        </div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon cyan">📡</div>
            <div class="stat-label">Total Captures</div>
            <div class="stat-value" id="stat-total">-</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon green">✅</div>
            <div class="stat-label">Successful</div>
            <div class="stat-value" id="stat-success">-</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon purple">🔑</div>
            <div class="stat-label">PMKID Found</div>
            <div class="stat-value" id="stat-pmkid">-</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-icon orange">🤝</div>
            <div class="stat-label">EAPOL</div>
            <div class="stat-value" id="stat-eapol">-</div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <span class="card-title">🔐 Crackable Handshakes</span>
            <a href="/api/captures/crackable" class="btn btn-secondary">View JSON</a>
        </div>
        <div id="crackable-list">
            <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                Loading...
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <span class="card-title">🚀 Start New Capture</span>
        </div>
        <form id="capture-form" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; align-items: end;">
            <div>
                <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">BSSID *</label>
                <input type="text" id="bssid" placeholder="AA:BB:CC:DD:EE:FF" required
                    style="width: 100%; padding: 10px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary);">
            </div>
            <div>
                <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">SSID</label>
                <input type="text" id="ssid" placeholder="NetworkName"
                    style="width: 100%; padding: 10px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary);">
            </div>
            <div>
                <label style="display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">Channel</label>
                <input type="number" id="channel" placeholder="6" min="1" max="200"
                    style="width: 100%; padding: 10px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary);">
            </div>
            <button type="submit" class="btn btn-primary">🎯 Start Capture</button>
        </form>
        <div id="capture-result" style="margin-top: 16px;"></div>
    </div>
    
    <script>
        // Load stats
        async function loadStats() {
            try {
                const resp = await fetch('/api/captures/stats');
                const data = await resp.json();
                document.getElementById('stat-total').textContent = data.total_captures || 0;
                document.getElementById('stat-success').textContent = data.successful_captures || 0;
                document.getElementById('stat-pmkid').textContent = data.pmkids_found || 0;
                document.getElementById('stat-eapol').textContent = data.eapol_handshakes || 0;
                document.getElementById('capture-status').textContent = 
                    data.active_sessions > 0 ? `${data.active_sessions} Active` : 'Idle';
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        }
        
        // Load crackable
        async function loadCrackable() {
            try {
                const resp = await fetch('/api/captures/crackable');
                const data = await resp.json();
                const list = document.getElementById('crackable-list');
                
                if (!data.items || data.items.length === 0) {
                    list.innerHTML = `
                        <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                            <div style="font-size: 32px; margin-bottom: 12px;">🔓</div>
                            <div>No crackable handshakes yet</div>
                        </div>
                    `;
                    return;
                }
                
                let html = '<table><thead><tr><th>BSSID</th><th>SSID</th><th>Type</th><th>Action</th></tr></thead><tbody>';
                data.items.forEach(item => {
                    const type = item.pmkid_found ? 'PMKID' : `EAPOL (${item.eapol_count})`;
                    html += `
                        <tr>
                            <td><code style="color: var(--accent-cyan);">${item.bssid}</code></td>
                            <td>${item.ssid || '<hidden>'}</td>
                            <td><span class="badge badge-success">${type}</span></td>
                            <td>
                                ${item.hashcat_path ? 
                                    `<a href="/api/captures/${item.id}/download?format=hashcat" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;">⬇️ .22000</a>` : 
                                    '-'
                                }
                            </td>
                        </tr>
                    `;
                });
                html += '</tbody></table>';
                list.innerHTML = html;
            } catch (e) {
                console.error('Failed to load crackable:', e);
            }
        }
        
        // Start capture
        document.getElementById('capture-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const result = document.getElementById('capture-result');
            result.innerHTML = '<div class="badge badge-info">Starting capture...</div>';
            
            try {
                const resp = await fetch('/api/captures', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        bssid: document.getElementById('bssid').value,
                        ssid: document.getElementById('ssid').value || '<hidden>',
                        channel: parseInt(document.getElementById('channel').value) || 0,
                    })
                });
                const data = await resp.json();
                
                if (data.ok) {
                    result.innerHTML = `<div class="badge badge-success">✅ Capture started: ${data.capture.status}</div>`;
                    loadStats();
                    loadCrackable();
                } else {
                    result.innerHTML = `<div class="badge badge-danger">❌ ${data.error}</div>`;
                }
            } catch (e) {
                result.innerHTML = `<div class="badge badge-danger">❌ ${e.message}</div>`;
            }
        });
        
        // Initial load
        loadStats();
        loadCrackable();
        setInterval(loadStats, 5000);
    </script>
    """
    return render_template_string(_BASE, title=cfg.web.title, active="captures", content=content)


@ui_bp.route("/bluetooth")
def bluetooth_page():
    """BLE Scanner page."""
    cfg = _cfg()
    content = """
    <h1 class="page-title">📶 Bluetooth Scanner</h1>
    
    <div class="stat-grid">
        <div class="stat-card">
            <span class="stat-value" id="total-devices">0</span>
            <span class="stat-label">Total Devices</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="total-beacons">0</span>
            <span class="stat-label">Beacons</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="ibeacons">0</span>
            <span class="stat-label">iBeacons</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="scans">0</span>
            <span class="stat-label">Scans</span>
        </div>
    </div>
    
    <div class="card-grid">
        <div class="card">
            <div class="card-header">
                <span class="card-title">📱 Recent Devices</span>
                <button class="btn btn-primary" id="refresh-btn">Refresh</button>
            </div>
            <div class="card-body">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>MAC</th>
                            <th>RSSI</th>
                            <th>Type</th>
                            <th>Last Seen</th>
                        </tr>
                    </thead>
                    <tbody id="devices-list">
                        <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span class="card-title">📍 Beacons</span>
            </div>
            <div class="card-body">
                <div id="beacons-list">
                    <p>No beacons detected yet.</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card" style="margin-top: 20px;">
        <div class="card-header">
            <span class="card-title">🔧 Controls</span>
        </div>
        <div class="card-body">
            <button class="btn btn-danger" id="clear-btn">Clear Cache</button>
            <span id="status-msg" style="margin-left: 20px;"></span>
        </div>
    </div>
    
    <script>
        async function loadStats() {
            try {
                const resp = await fetch('/api/ble/stats');
                if (!resp.ok) {
                    document.getElementById('status-msg').textContent = 'Scanner not available';
                    return;
                }
                const data = await resp.json();
                document.getElementById('total-devices').textContent = data.momo_ble_devices_total || 0;
                document.getElementById('total-beacons').textContent = data.momo_ble_beacons_total || 0;
                document.getElementById('ibeacons').textContent = data.momo_ble_ibeacons || 0;
                document.getElementById('scans').textContent = data.momo_ble_scans_total || 0;
            } catch (e) {
                console.error(e);
            }
        }
        
        async function loadDevices() {
            try {
                const resp = await fetch('/api/ble/devices?limit=50');
                if (!resp.ok) return;
                const data = await resp.json();
                const tbody = document.getElementById('devices-list');
                
                if (!data.devices || data.devices.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5">No devices found. Enable BLE scanning in config.</td></tr>';
                    return;
                }
                
                tbody.innerHTML = data.devices.map(d => `
                    <tr>
                        <td>${d.name || '<unknown>'}</td>
                        <td><code>${d.address}</code></td>
                        <td>${d.rssi} dBm</td>
                        <td><span class="badge ${d.beacon_type !== 'unknown' ? 'badge-success' : 'badge-secondary'}">${d.beacon_type}</span></td>
                        <td>${d.last_seen ? new Date(d.last_seen).toLocaleTimeString() : '-'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }
        
        async function loadBeacons() {
            try {
                const resp = await fetch('/api/ble/beacons?limit=20');
                if (!resp.ok) return;
                const data = await resp.json();
                const container = document.getElementById('beacons-list');
                
                if (!data.beacons || data.beacons.length === 0) {
                    container.innerHTML = '<p>No beacons detected yet.</p>';
                    return;
                }
                
                container.innerHTML = data.beacons.map(b => `
                    <div style="background: var(--bg-card-hover); padding: 12px; border-radius: 8px; margin-bottom: 8px;">
                        <strong>${b.name || b.address}</strong>
                        <span class="badge badge-info" style="margin-left: 8px;">${b.beacon_type}</span>
                        <br>
                        ${b.uuid ? `<small>UUID: ${b.uuid}</small><br>` : ''}
                        ${b.major !== null ? `<small>Major: ${b.major}, Minor: ${b.minor}</small>` : ''}
                    </div>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }
        
        document.getElementById('refresh-btn').addEventListener('click', () => {
            loadStats();
            loadDevices();
            loadBeacons();
        });
        
        document.getElementById('clear-btn').addEventListener('click', async () => {
            try {
                await fetch('/api/ble/clear', {method: 'POST'});
                document.getElementById('status-msg').textContent = 'Cache cleared!';
                loadStats();
                loadDevices();
                loadBeacons();
            } catch (e) {
                document.getElementById('status-msg').textContent = 'Error: ' + e.message;
            }
        });
        
        // Initial load
        loadStats();
        loadDevices();
        loadBeacons();
        setInterval(loadStats, 5000);
        setInterval(loadDevices, 10000);
    </script>
    """
    return render_template_string(_BASE, title=cfg.web.title, active="bluetooth", content=content)


@ui_bp.route("/eviltwin")
def eviltwin_page():
    """Evil Twin attack page."""
    cfg = _cfg()
    content = """
    <h1 class="page-title">👿 Evil Twin</h1>
    
    <div class="stat-grid">
        <div class="stat-card">
            <span class="stat-value" id="status">Stopped</span>
            <span class="stat-label">Status</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="clients">0</span>
            <span class="stat-label">Connected</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="creds">0</span>
            <span class="stat-label">Credentials</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" id="ssid">-</span>
            <span class="stat-label">SSID</span>
        </div>
    </div>
    
    <div class="card-grid">
        <div class="card">
            <div class="card-header">
                <span class="card-title">🚀 Start Attack</span>
            </div>
            <div class="card-body">
                <form id="attack-form">
                    <div class="form-group">
                        <label>Target SSID</label>
                        <input type="text" id="target-ssid" placeholder="FreeWiFi" value="FreeWiFi" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; background:var(--bg-card); color:var(--text-primary);">
                    </div>
                    <div class="form-group" style="margin-top:15px;">
                        <label>Channel</label>
                        <input type="number" id="channel" value="6" min="1" max="14" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; background:var(--bg-card); color:var(--text-primary);">
                    </div>
                    <div class="form-group" style="margin-top:15px;">
                        <label>Portal Template</label>
                        <select id="template" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; background:var(--bg-card); color:var(--text-primary);">
                            <option value="generic">Generic WiFi</option>
                            <option value="hotel">Hotel Guest</option>
                            <option value="corporate">Corporate</option>
                            <option value="facebook">Facebook</option>
                            <option value="google">Google</option>
                            <option value="router">Router Login</option>
                        </select>
                    </div>
                    <div style="margin-top:20px; display:flex; gap:10px;">
                        <button type="submit" class="btn btn-primary" id="start-btn">Start Attack</button>
                        <button type="button" class="btn btn-danger" id="stop-btn">Stop</button>
                    </div>
                </form>
                <div id="attack-result" style="margin-top:15px;"></div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <span class="card-title">💀 Captured Credentials</span>
            </div>
            <div class="card-body">
                <div id="creds-list" style="max-height:400px; overflow-y:auto;">
                    <p style="color:var(--text-muted);">No credentials captured yet.</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card" style="margin-top:20px;">
        <div class="card-header">
            <span class="card-title">📱 Connected Clients</span>
        </div>
        <div class="card-body">
            <table class="table">
                <thead>
                    <tr>
                        <th>MAC Address</th>
                        <th>IP Address</th>
                        <th>Connected At</th>
                        <th>Credentials</th>
                    </tr>
                </thead>
                <tbody id="clients-list">
                    <tr><td colspan="4" style="color:var(--text-muted);">No clients connected.</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        async function loadStatus() {
            try {
                const resp = await fetch('/api/eviltwin/status');
                if (!resp.ok) return;
                const data = await resp.json();
                
                document.getElementById('status').textContent = data.status || 'stopped';
                document.getElementById('clients').textContent = data.clients_connected || 0;
                document.getElementById('creds').textContent = data.credentials_captured || 0;
                document.getElementById('ssid').textContent = data.current_ssid || '-';
                
                const statusEl = document.getElementById('status');
                statusEl.style.color = data.status === 'running' ? 'var(--accent-green)' : 'var(--text-muted)';
            } catch (e) {
                console.error(e);
            }
        }
        
        async function loadCredentials() {
            try {
                const resp = await fetch('/api/eviltwin/credentials');
                if (!resp.ok) return;
                const data = await resp.json();
                
                const container = document.getElementById('creds-list');
                if (!data.credentials || data.credentials.length === 0) {
                    container.innerHTML = '<p style="color:var(--text-muted);">No credentials captured yet.</p>';
                    return;
                }
                
                container.innerHTML = data.credentials.reverse().map(c => `
                    <div style="background:var(--bg-card-hover); padding:12px; border-radius:8px; margin-bottom:8px; border-left:3px solid var(--accent-red);">
                        <div style="display:flex; justify-content:space-between;">
                            <strong style="color:var(--accent-cyan);">${c.username}</strong>
                            <small style="color:var(--text-muted);">${c.timestamp}</small>
                        </div>
                        <div style="color:var(--accent-orange); font-family:monospace; margin-top:5px;">🔑 ${c.password}</div>
                        <small style="color:var(--text-muted);">${c.client_ip} | ${c.ssid}</small>
                    </div>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }
        
        async function loadClients() {
            try {
                const resp = await fetch('/api/eviltwin/clients');
                if (!resp.ok) return;
                const data = await resp.json();
                
                const tbody = document.getElementById('clients-list');
                if (!data.clients || data.clients.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);">No clients connected.</td></tr>';
                    return;
                }
                
                tbody.innerHTML = data.clients.map(c => `
                    <tr>
                        <td><code>${c.mac_address}</code></td>
                        <td>${c.ip_address || '-'}</td>
                        <td>${c.connected_at}</td>
                        <td>${c.credentials_captured ? '<span class="badge badge-success">✓</span>' : '-'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }
        
        document.getElementById('attack-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const result = document.getElementById('attack-result');
            result.innerHTML = '<span style="color:var(--accent-cyan);">Starting attack...</span>';
            
            try {
                const resp = await fetch('/api/eviltwin/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        ssid: document.getElementById('target-ssid').value,
                        channel: parseInt(document.getElementById('channel').value),
                        template: document.getElementById('template').value,
                    })
                });
                const data = await resp.json();
                
                if (data.ok) {
                    result.innerHTML = '<span style="color:var(--accent-green);">✅ Attack started!</span>';
                    loadStatus();
                } else {
                    result.innerHTML = `<span style="color:var(--accent-red);">❌ ${data.error}</span>`;
                }
            } catch (e) {
                result.innerHTML = `<span style="color:var(--accent-red);">❌ ${e.message}</span>`;
            }
        });
        
        document.getElementById('stop-btn').addEventListener('click', async () => {
            const result = document.getElementById('attack-result');
            try {
                await fetch('/api/eviltwin/stop', {method: 'POST'});
                result.innerHTML = '<span style="color:var(--text-muted);">Attack stopped.</span>';
                loadStatus();
            } catch (e) {
                result.innerHTML = `<span style="color:var(--accent-red);">❌ ${e.message}</span>`;
            }
        });
        
        // Initial load and auto-refresh
        loadStatus();
        loadCredentials();
        loadClients();
        setInterval(loadStatus, 3000);
        setInterval(loadCredentials, 5000);
        setInterval(loadClients, 5000);
    </script>
    """
    return render_template_string(_BASE, title=cfg.web.title, active="eviltwin", content=content)
