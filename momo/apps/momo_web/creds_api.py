"""Credential Harvesting API endpoints.

REST API for controlling and monitoring credential harvesting.
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/creds", tags=["credentials"])


# Request/Response Models
class CredsConfigRequest(BaseModel):
    """Credential harvesting configuration."""
    interface: str = Field(default="eth0", description="Network interface")
    enable_responder: bool = Field(default=True, description="Enable LLMNR/NBT-NS poisoning")
    enable_ntlm: bool = Field(default=True, description="Enable NTLM capture")
    enable_http: bool = Field(default=True, description="Enable HTTP auth sniffing")
    enable_kerberos: bool = Field(default=False, description="Enable Kerberos attacks")
    dc_ip: Optional[str] = Field(default=None, description="Domain Controller IP")
    domain: Optional[str] = Field(default=None, description="AD Domain name")


class CredsStatsResponse(BaseModel):
    """Credential harvesting statistics."""
    running: bool
    uptime_seconds: float
    total_credentials: int
    ntlm_hashes: int
    http_credentials: int
    poisoned_queries: int
    kerberos_tickets: int


class CredentialItem(BaseModel):
    """Single captured credential."""
    type: str
    timestamp: str
    source_ip: Optional[str] = None
    username: Optional[str] = None
    domain: Optional[str] = None
    hash_value: Optional[str] = None


class ExportRequest(BaseModel):
    """Export request."""
    directory: str = Field(default="/tmp/creds", description="Export directory")
    format: str = Field(default="hashcat", description="Export format (hashcat, john, csv)")


class ExportResponse(BaseModel):
    """Export result."""
    success: bool
    files: dict
    total_exported: int


# Dependency to get creds manager
async def get_creds_manager():
    """Get CredsManager from app state."""
    from fastapi import Request
    # This would be injected via app.state
    # Placeholder for now
    return None


@router.get("/status", response_model=CredsStatsResponse)
async def get_status(manager=Depends(get_creds_manager)):
    """Get credential harvesting status."""
    if not manager:
        return CredsStatsResponse(
            running=False,
            uptime_seconds=0,
            total_credentials=0,
            ntlm_hashes=0,
            http_credentials=0,
            poisoned_queries=0,
            kerberos_tickets=0,
        )
    
    stats = manager.stats
    return CredsStatsResponse(
        running=stats['running'],
        uptime_seconds=stats['uptime'],
        total_credentials=stats['total_credentials'],
        ntlm_hashes=stats['ntlm_hashes'],
        http_credentials=stats['http_credentials'],
        poisoned_queries=stats['poisoned_queries'],
        kerberos_tickets=stats['kerberos_tickets'],
    )


@router.post("/start")
async def start_harvesting(
    config: Optional[CredsConfigRequest] = None,
    manager=Depends(get_creds_manager)
):
    """Start credential harvesting."""
    if not manager:
        raise HTTPException(status_code=500, detail="CredsManager not initialized")
    
    try:
        await manager.start()
        return {"status": "started", "message": "Credential harvesting started"}
    except Exception as e:
        logger.error(f"Failed to start creds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_harvesting(manager=Depends(get_creds_manager)):
    """Stop credential harvesting."""
    if not manager:
        raise HTTPException(status_code=500, detail="CredsManager not initialized")
    
    try:
        await manager.stop()
        return {"status": "stopped", "message": "Credential harvesting stopped"}
    except Exception as e:
        logger.error(f"Failed to stop creds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/credentials")
async def get_credentials(
    limit: int = 100,
    offset: int = 0,
    cred_type: Optional[str] = None,
    manager=Depends(get_creds_manager)
):
    """Get captured credentials."""
    if not manager:
        return {"credentials": [], "total": 0}
    
    all_creds = manager.all_credentials
    
    # Filter by type if specified
    if cred_type:
        all_creds = [c for c in all_creds if c['type'] == cred_type]
    
    total = len(all_creds)
    creds = all_creds[offset:offset + limit]
    
    return {
        "credentials": creds,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/ntlm")
async def get_ntlm_hashes(manager=Depends(get_creds_manager)):
    """Get captured NTLM hashes."""
    if not manager or not manager._ntlm:
        return {"hashes": [], "total": 0}
    
    hashes = manager._ntlm.hashes
    return {
        "hashes": [
            {
                "timestamp": h.timestamp.isoformat(),
                "version": h.version.name,
                "username": h.username,
                "domain": h.domain,
                "source_ip": h.source_ip,
                "hashcat_format": h.hashcat_format,
            }
            for h in hashes
        ],
        "total": len(hashes),
        "challenge": manager._ntlm.challenge,
    }


@router.get("/http")
async def get_http_credentials(manager=Depends(get_creds_manager)):
    """Get captured HTTP credentials."""
    if not manager or not manager._http:
        return {"credentials": [], "total": 0}
    
    creds = manager._http.credentials
    return {
        "credentials": [
            {
                "timestamp": c.timestamp.isoformat(),
                "type": c.auth_type.name,
                "host": c.host,
                "path": c.path,
                "username": c.username,
                "password": c.password if c.password else "[hidden]",
                "source_ip": c.source_ip,
            }
            for c in creds
        ],
        "total": len(creds),
    }


@router.get("/kerberos")
async def get_kerberos_tickets(manager=Depends(get_creds_manager)):
    """Get captured Kerberos tickets."""
    if not manager or not manager._kerberos:
        return {"tickets": [], "total": 0}
    
    tickets = manager._kerberos.tickets
    return {
        "tickets": [
            {
                "timestamp": t.timestamp.isoformat(),
                "username": t.username,
                "domain": t.domain,
                "spn": t.spn,
                "enc_type": t.enc_type.name,
                "hashcat_format": t.hashcat_format,
            }
            for t in tickets
        ],
        "total": len(tickets),
    }


@router.post("/export", response_model=ExportResponse)
async def export_credentials(
    request: ExportRequest,
    manager=Depends(get_creds_manager)
):
    """Export credentials to files."""
    if not manager:
        raise HTTPException(status_code=500, detail="CredsManager not initialized")
    
    try:
        counts = manager.export_all(request.directory)
        return ExportResponse(
            success=True,
            files=counts,
            total_exported=sum(counts.values()),
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_credentials(manager=Depends(get_creds_manager)):
    """Clear all captured credentials."""
    if not manager:
        raise HTTPException(status_code=500, detail="CredsManager not initialized")
    
    # Clear all collections
    if manager._ntlm:
        manager._ntlm._hashes.clear()
    if manager._http:
        manager._http.clear()
    if manager._responder:
        manager._responder.clear_queries()
    manager._all_creds.clear()
    
    return {"status": "cleared", "message": "All credentials cleared"}

