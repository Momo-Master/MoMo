"""Cracking REST API - Endpoints for hashcat job management."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
cracking_bp = Blueprint("cracking", __name__, url_prefix="/api/cracking")


def _get_plugin() -> Any:
    """Get cracker plugin instance."""
    try:
        from momo.apps.momo_plugins import hashcat_cracker
        return hashcat_cracker
    except ImportError:
        return None


@cracking_bp.route("/status", methods=["GET"])
def get_status():
    """Get cracker plugin status."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503
    return jsonify(plugin.get_status())


@cracking_bp.route("/jobs", methods=["GET"])
def list_jobs():
    """List crack jobs."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503

    limit = request.args.get("limit", 50, type=int)
    jobs = plugin.get_jobs(limit=limit)
    return jsonify({"jobs": jobs, "total": len(jobs)})


@cracking_bp.route("/jobs", methods=["POST"])
def start_job():
    """Start a new crack job."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503

    data = request.get_json() or {}
    hash_file = data.get("hash_file")

    if not hash_file:
        return jsonify({"error": "hash_file required"}), 400

    if not Path(hash_file).exists():
        return jsonify({"error": "Hash file not found"}), 404

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            plugin.crack_file(
                hash_file=Path(hash_file),
                wordlist=data.get("wordlist"),
                attack_mode=data.get("attack_mode", 0),
                mask=data.get("mask"),
            )
        )
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cracking_bp.route("/jobs/<job_id>", methods=["DELETE"])
def stop_job(job_id: str):
    """Stop a running job."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(plugin.stop_job(job_id))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cracking_bp.route("/cracked", methods=["GET"])
def list_cracked():
    """List cracked passwords."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503

    limit = request.args.get("limit", 50, type=int)
    cracked = plugin.get_cracked(limit=limit)
    return jsonify({"cracked": cracked, "total": len(cracked)})


@cracking_bp.route("/wordlists", methods=["GET"])
def list_wordlists():
    """List available wordlists."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503

    wordlists = plugin.get_wordlists()
    return jsonify({"wordlists": wordlists, "total": len(wordlists)})


@cracking_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get cracking statistics."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Cracker not available"}), 503

    return jsonify(plugin.get_metrics())


# ========== John the Ripper Endpoints ==========

_john_manager = None


def _get_john():
    global _john_manager
    if _john_manager is None:
        from momo.infrastructure.cracking import MockJohnManager
        _john_manager = MockJohnManager()
    return _john_manager


@cracking_bp.route("/john/status", methods=["GET"])
def john_status():
    """Get John the Ripper status."""
    john = _get_john()
    return jsonify({
        "running": john._running,
        **john.stats.to_dict(),
        **john.get_metrics(),
    })


@cracking_bp.route("/john/jobs", methods=["GET"])
def john_list_jobs():
    """List John cracking jobs."""
    john = _get_john()
    jobs = [j.to_dict() for j in john.get_all_jobs()]
    return jsonify({"jobs": jobs, "total": len(jobs)})


@cracking_bp.route("/john/jobs", methods=["POST"])
async def john_start_job():
    """Start a new John cracking job."""
    john = _get_john()
    data = request.get_json() or {}
    
    hash_file = data.get("hash_file")
    if not hash_file:
        return jsonify({"error": "hash_file required"}), 400
    
    hash_path = Path(hash_file)
    if not hash_path.exists():
        return jsonify({"error": "Hash file not found"}), 404
    
    mode_str = data.get("mode", "wordlist")
    from momo.infrastructure.cracking import JohnMode
    mode = JohnMode(mode_str)
    
    wordlist = data.get("wordlist")
    wordlist_path = Path(wordlist) if wordlist else None
    
    job = await john.crack_file(
        hash_file=hash_path,
        mode=mode,
        wordlist=wordlist_path,
        mask=data.get("mask"),
        rules=data.get("rules"),
        format=data.get("format", "wpapsk"),
    )
    
    return jsonify(job.to_dict())


@cracking_bp.route("/john/jobs/<job_id>", methods=["GET"])
def john_get_job(job_id: str):
    """Get a specific John job."""
    john = _get_john()
    job = john.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict())


@cracking_bp.route("/john/jobs/<job_id>", methods=["DELETE"])
async def john_stop_job(job_id: str):
    """Stop a John job."""
    john = _get_john()
    success = await john.stop_job(job_id)
    return jsonify({"success": success})


@cracking_bp.route("/john/convert", methods=["POST"])
async def john_convert():
    """Convert hccapx to John format."""
    john = _get_john()
    data = request.get_json() or {}
    
    input_file = data.get("input_file")
    if not input_file:
        return jsonify({"error": "input_file required"}), 400
    
    input_path = Path(input_file)
    if not input_path.exists():
        return jsonify({"error": "Input file not found"}), 404
    
    output = await john.convert_hccapx(input_path)
    if output:
        return jsonify({"output_file": str(output), "success": True})
    else:
        return jsonify({"error": "Conversion failed", "success": False}), 500


@cracking_bp.route("/john/show", methods=["POST"])
async def john_show():
    """Show cracked passwords for a hash file."""
    john = _get_john()
    data = request.get_json() or {}
    
    hash_file = data.get("hash_file")
    if not hash_file:
        return jsonify({"error": "hash_file required"}), 400
    
    passwords = await john.show_cracked(Path(hash_file))
    return jsonify({"passwords": passwords, "count": len(passwords)})

