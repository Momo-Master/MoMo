from __future__ import annotations

import json

from flask import Blueprint, current_app, redirect, render_template_string, url_for

from ...config import MomoConfig

pages_bp = Blueprint("pages", __name__)


def _cfg() -> MomoConfig:
    return current_app.config["MOMO_CONFIG"]


_BASE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <title>MoMo</title>
  <style> body { padding: 1rem; } </style>
</head>
<body class="bg-gray-50 text-gray-900">
  <div class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-semibold mb-4">MoMo</h1>
    <div class="mb-4">{{ content|safe }}</div>
  </div>
</body>
</html>
"""


@pages_bp.get("/")
def index():
    cfg = _cfg()
    meta = cfg.meta_dir / "stats.json"
    data = {}
    if meta.exists():
        data = json.loads(meta.read_text(encoding="utf-8"))
    content = f"""
    <div class='grid grid-cols-2 gap-4'>
      <div class='p-4 bg-white shadow rounded'>
        <div class='text-sm text-gray-500'>Mode</div>
        <div class='text-xl'>{cfg.mode.value}</div>
      </div>
      <div class='p-4 bg-white shadow rounded'>
        <div class='text-sm text-gray-500'>Channel</div>
        <div class='text-xl'>{data.get('channel','-')}</div>
      </div>
      <div class='p-4 bg-white shadow rounded'>
        <div class='text-sm text-gray-500'>Files</div>
        <div class='text-xl'>{data.get('files','-')}</div>
      </div>
      <div class='p-4 bg-white shadow rounded'>
        <div class='text-sm text-gray-500'>Bytes</div>
        <div class='text-xl'>{data.get('bytes','-')}</div>
      </div>
    </div>
    <div class='mt-4'>
      <a class='text-blue-600 underline' href='{url_for('pages.handshakes')}'>Handshakes</a>
      <span class='mx-2'>|</span>
      <a class='text-blue-600 underline' href='{url_for('pages.metrics')}'>Metrics</a>
      <span class='mx-2'>|</span>
      <a class='text-blue-600 underline' href='{url_for('pages.about')}'>About</a>
    </div>
    """
    return render_template_string(_BASE, content=content)


@pages_bp.get("/handshakes")
def handshakes():
    from pathlib import Path

    cfg = _cfg()
    rows = []
    for p in sorted(Path(cfg.handshakes_dir).glob("*.pcapng")):
        rows.append(f"<tr><td class='px-2 py-1'>{p.name}</td><td class='px-2 py-1'>{p.stat().st_size}</td><td class='px-2 py-1'><a class='text-blue-600 underline' href='/api/handshakes/{p.name}'>Download</a></td></tr>")
    table = """
    <table class='min-w-full bg-white shadow rounded'>
      <thead><tr><th class='px-2 py-1 text-left'>File</th><th class='px-2 py-1 text-left'>Size</th><th class='px-2 py-1'>Action</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """.replace("{rows}", "\n".join(rows))
    return render_template_string(_BASE, content=table)


@pages_bp.get("/metrics")
def metrics():
    return redirect("/api/metrics")


@pages_bp.get("/about")
def about():
    content = """
    <div class='p-4 bg-white shadow rounded'>
      <div class='text-sm text-gray-500'>Version</div>
      <div class='text-xl'>MoMo</div>
    </div>
    """
    return render_template_string(_BASE, content=content)


