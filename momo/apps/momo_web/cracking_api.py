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

