"""
Cracking REST API - Endpoints for John the Ripper job management.

NOTE: GPU-based Hashcat cracking has been moved to Cloud infrastructure.
For heavy cracking jobs, use Nexus → Cloud GPU VPS integration.
See docs/CRACKING.md for details.
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
cracking_bp = Blueprint("cracking", __name__, url_prefix="/api/cracking")

# ========== John the Ripper Endpoints ==========

_john_manager = None


def _get_john():
    """Get John the Ripper manager (lazy init)."""
    global _john_manager
    if _john_manager is None:
        from momo.infrastructure.cracking import MockJohnManager
        _john_manager = MockJohnManager()
    return _john_manager


@cracking_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get cracking status.
    
    Returns:
        {
            "running": bool,
            "note": "GPU cracking moved to Cloud - use Nexus API",
            "john": {...}
        }
    """
    john = _get_john()
    return jsonify({
        "running": john._running,
        "note": "GPU cracking (Hashcat) moved to Cloud VPS - use Nexus API for heavy jobs",
        "local_cracker": "john",
        "john": john.stats.to_dict(),
        "metrics": john.get_metrics(),
    })


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


# ========== Cloud Cracking Proxy (TODO: Nexus Integration) ==========

@cracking_bp.route("/cloud/status", methods=["GET"])
def cloud_status():
    """
    Check Cloud GPU VPS status.
    
    This endpoint will proxy to Nexus which manages Cloud cracking infrastructure.
    """
    return jsonify({
        "status": "not_configured",
        "message": "Cloud cracking requires Nexus integration",
        "setup_guide": "See docs/CRACKING.md for Cloud GPU setup",
    })


@cracking_bp.route("/cloud/submit", methods=["POST"])
def cloud_submit():
    """
    Submit a cracking job to Cloud GPU VPS.
    
    This endpoint will proxy to Nexus for Cloud cracking.
    Currently not implemented - requires Nexus integration.
    """
    return jsonify({
        "error": "Cloud cracking not yet configured",
        "message": "Use Nexus API to submit jobs to Cloud GPU VPS",
        "setup_guide": "See docs/CRACKING.md",
    }), 503
