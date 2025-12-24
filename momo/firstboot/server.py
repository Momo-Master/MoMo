"""
First Boot Wizard Web Server.

FastAPI application that serves the setup wizard:
- Static SPA frontend
- REST API for wizard steps
- WiFi scanning
- Nexus discovery and registration
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class WizardStep(str, Enum):
    """Wizard steps."""
    WELCOME = "welcome"
    PASSWORD = "password"
    NETWORK = "network"
    PROFILE = "profile"
    NEXUS = "nexus"
    SUMMARY = "summary"
    COMPLETE = "complete"


class WizardState(BaseModel):
    """Current wizard state."""
    current_step: WizardStep = WizardStep.WELCOME
    language: str = "en"
    started_at: datetime = Field(default_factory=datetime.now)
    completed: bool = False


class LanguageRequest(BaseModel):
    """Language selection request."""
    language: str = Field(..., pattern="^(en|tr)$")


class PasswordRequest(BaseModel):
    """Password setup request."""
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class NetworkRequest(BaseModel):
    """Network configuration request."""
    mode: str = Field(..., pattern="^(ap|client)$")
    ap_ssid: str = Field(default="MoMo-Management")
    ap_password: str = Field(default="")
    ap_channel: int = Field(default=6, ge=1, le=14)
    client_ssid: str = Field(default="")
    client_password: str = Field(default="")


class ProfileRequest(BaseModel):
    """Profile selection request."""
    profile: str = Field(..., pattern="^(passive|balanced|aggressive)$")


class NexusRequest(BaseModel):
    """Nexus configuration request."""
    enabled: bool = False
    url: str = ""
    token: str = ""
    device_name: str = ""


class CompleteRequest(BaseModel):
    """Final setup request."""
    confirm: bool = True


class WifiNetwork(BaseModel):
    """WiFi network scan result."""
    ssid: str
    bssid: str
    signal: int
    encryption: str


class NexusDevice(BaseModel):
    """Discovered Nexus device."""
    name: str
    ip: str
    port: int
    version: str
    devices_connected: int = 0


# =============================================================================
# Wizard Server
# =============================================================================

class WizardServer:
    """
    First Boot Wizard Server.
    
    Manages the setup wizard state and API endpoints.
    """
    
    def __init__(
        self,
        network_manager=None,
        nexus_discovery=None,
        config_generator=None,
        static_dir: Optional[Path] = None,
    ):
        """
        Initialize wizard server.
        
        Args:
            network_manager: NetworkManager instance
            nexus_discovery: NexusDiscovery instance
            config_generator: ConfigGenerator instance
            static_dir: Path to static files for frontend
        """
        self.network_manager = network_manager
        self.nexus_discovery = nexus_discovery
        self.config_generator = config_generator
        self.static_dir = static_dir or Path(__file__).parent / "static"
        
        # Wizard state
        self.state = WizardState()
        self.config_data: dict = {}
        
        # Create FastAPI app
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI application."""
        app = FastAPI(
            title="MoMo First Boot Wizard",
            version="1.0.0",
            docs_url="/api/docs",
            redoc_url=None,
        )
        
        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes(app)
        
        # Mount static files if directory exists
        if self.static_dir.exists():
            app.mount("/static", StaticFiles(directory=self.static_dir), name="static")
        
        return app
    
    def _register_routes(self, app: FastAPI):
        """Register API routes."""
        
        # =====================================================================
        # Index / SPA
        # =====================================================================
        
        @app.get("/", response_class=HTMLResponse)
        async def index():
            """Serve the wizard SPA."""
            index_path = self.static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            
            # Fallback: minimal HTML for development
            return HTMLResponse(self._get_fallback_html())
        
        @app.get("/generate_204")
        @app.get("/hotspot-detect.html")
        @app.get("/connecttest.txt")
        async def captive_portal_check():
            """Handle captive portal detection requests."""
            # Redirect to wizard
            return Response(
                status_code=302,
                headers={"Location": "/"}
            )
        
        # =====================================================================
        # Wizard Status API
        # =====================================================================
        
        @app.get("/api/status")
        async def get_status():
            """Get current wizard status."""
            return {
                "current_step": self.state.current_step.value,
                "language": self.state.language,
                "started_at": self.state.started_at.isoformat(),
                "completed": self.state.completed,
                "config": self._get_safe_config(),
            }
        
        @app.get("/api/network/status")
        async def get_network_status():
            """Get network status."""
            if self.network_manager:
                return self.network_manager.get_state()
            return {"ap_running": False, "dhcp_running": False}
        
        # =====================================================================
        # Step 1: Language
        # =====================================================================
        
        @app.post("/api/step/language")
        async def set_language(request: LanguageRequest):
            """Set language preference."""
            self.state.language = request.language
            self.config_data["language"] = request.language
            self.state.current_step = WizardStep.PASSWORD
            
            return {
                "success": True,
                "next_step": self.state.current_step.value,
            }
        
        # =====================================================================
        # Step 2: Password
        # =====================================================================
        
        @app.post("/api/step/password")
        async def set_password(request: PasswordRequest):
            """Set admin password."""
            if request.password != request.confirm_password:
                raise HTTPException(
                    status_code=400,
                    detail="Passwords do not match"
                )
            
            if len(request.password) < 8:
                raise HTTPException(
                    status_code=400,
                    detail="Password must be at least 8 characters"
                )
            
            # Hash password
            import hashlib
            password_hash = hashlib.sha256(request.password.encode()).hexdigest()
            
            self.config_data["admin_password_hash"] = password_hash
            self.state.current_step = WizardStep.NETWORK
            
            return {
                "success": True,
                "next_step": self.state.current_step.value,
            }
        
        # =====================================================================
        # Step 3: Network
        # =====================================================================
        
        @app.get("/api/wifi/scan")
        async def scan_wifi():
            """Scan for available WiFi networks."""
            if not self.network_manager:
                return {"networks": []}
            
            networks = await self.network_manager.scan_wifi_networks()
            return {"networks": networks}
        
        @app.post("/api/wifi/test")
        async def test_wifi(ssid: str, password: str):
            """Test WiFi connection."""
            if not self.network_manager:
                raise HTTPException(
                    status_code=503,
                    detail="Network manager not available"
                )
            
            result = await self.network_manager.test_wifi_connection(ssid, password)
            return result
        
        @app.post("/api/step/network")
        async def set_network(request: NetworkRequest):
            """Configure network settings."""
            # Validate based on mode
            if request.mode == "ap":
                if len(request.ap_password) < 8:
                    raise HTTPException(
                        status_code=400,
                        detail="AP password must be at least 8 characters"
                    )
            else:  # client mode
                if not request.client_ssid:
                    raise HTTPException(
                        status_code=400,
                        detail="Client SSID is required"
                    )
            
            self.config_data["network"] = {
                "mode": request.mode,
                "ap": {
                    "ssid": request.ap_ssid,
                    "password": request.ap_password,
                    "channel": request.ap_channel,
                },
                "client": {
                    "ssid": request.client_ssid,
                    "password": request.client_password,
                },
            }
            self.state.current_step = WizardStep.PROFILE
            
            return {
                "success": True,
                "next_step": self.state.current_step.value,
            }
        
        # =====================================================================
        # Step 4: Profile
        # =====================================================================
        
        @app.post("/api/step/profile")
        async def set_profile(request: ProfileRequest):
            """Set operation profile."""
            self.config_data["profile"] = request.profile
            self.state.current_step = WizardStep.NEXUS
            
            return {
                "success": True,
                "next_step": self.state.current_step.value,
            }
        
        # =====================================================================
        # Step 5: Nexus
        # =====================================================================
        
        @app.get("/api/nexus/discover")
        async def discover_nexus():
            """Discover Nexus devices on the network."""
            if not self.nexus_discovery:
                return {"devices": []}
            
            devices = await self.nexus_discovery.discover(timeout=5.0)
            return {"devices": devices}
        
        @app.post("/api/nexus/test")
        async def test_nexus(url: str, token: str = ""):
            """Test connection to Nexus."""
            if not self.nexus_discovery:
                raise HTTPException(
                    status_code=503,
                    detail="Nexus discovery not available"
                )
            
            result = await self.nexus_discovery.test_connection(url, token)
            return result
        
        @app.post("/api/nexus/register")
        async def register_nexus(url: str, token: str, device_name: str):
            """Register with Nexus."""
            if not self.nexus_discovery:
                raise HTTPException(
                    status_code=503,
                    detail="Nexus discovery not available"
                )
            
            result = await self.nexus_discovery.register(url, token, device_name)
            return result
        
        @app.post("/api/step/nexus")
        async def set_nexus(request: NexusRequest):
            """Configure Nexus connection."""
            self.config_data["nexus"] = {
                "enabled": request.enabled,
                "url": request.url,
                "device_name": request.device_name,
                # Token is stored securely, not in config
            }
            self.state.current_step = WizardStep.SUMMARY
            
            return {
                "success": True,
                "next_step": self.state.current_step.value,
            }
        
        # =====================================================================
        # Step 6: Complete
        # =====================================================================
        
        @app.get("/api/summary")
        async def get_summary():
            """Get configuration summary."""
            return {
                "config": self._get_safe_config(),
            }
        
        @app.post("/api/complete")
        async def complete_setup(request: CompleteRequest):
            """Complete the setup wizard."""
            if not request.confirm:
                raise HTTPException(
                    status_code=400,
                    detail="Confirmation required"
                )
            
            try:
                # Generate and save configuration
                if self.config_generator:
                    success = await self.config_generator.generate(self.config_data)
                    if not success:
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to save configuration"
                        )
                
                # Mark setup as complete
                self.state.completed = True
                self.state.current_step = WizardStep.COMPLETE
                
                # Schedule restart (give time for response)
                asyncio.create_task(self._schedule_restart())
                
                return {
                    "success": True,
                    "message": "Setup complete! MoMo will restart in 5 seconds.",
                    "redirect_to": self._get_redirect_url(),
                }
                
            except Exception as e:
                logger.error(f"Failed to complete setup: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )
        
        @app.post("/api/reset")
        async def reset_wizard():
            """Reset wizard to start over."""
            self.state = WizardState()
            self.config_data = {}
            
            return {"success": True, "message": "Wizard reset"}
    
    def _get_safe_config(self) -> dict:
        """Get config with sensitive data masked."""
        config = dict(self.config_data)
        
        # Mask passwords
        if "admin_password_hash" in config:
            config["admin_password_hash"] = "********"
        
        if "network" in config:
            network = dict(config["network"])
            if network.get("ap", {}).get("password"):
                network["ap"] = dict(network["ap"])
                network["ap"]["password"] = "********"
            if network.get("client", {}).get("password"):
                network["client"] = dict(network["client"])
                network["client"]["password"] = "********"
            config["network"] = network
        
        return config
    
    def _get_redirect_url(self) -> str:
        """Get URL to redirect to after setup."""
        network = self.config_data.get("network", {})
        
        if network.get("mode") == "ap":
            # Redirect to management AP
            return f"http://192.168.4.1:8082"
        else:
            # Client mode - IP will be different
            return "http://momo.local:8082"
    
    async def _schedule_restart(self):
        """Schedule system restart after setup."""
        await asyncio.sleep(5)
        
        # Stop wizard network
        if self.network_manager:
            await self.network_manager.stop_wizard_network()
        
        # In production, would restart MoMo service
        logger.info("Setup complete - would restart MoMo service here")
    
    def _get_fallback_html(self) -> str:
        """Generate fallback HTML for development."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MoMo First Boot Wizard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 480px;
            width: 100%;
            padding: 24px;
        }
        .card {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 32px;
            text-align: center;
        }
        .logo {
            font-size: 48px;
            margin-bottom: 16px;
        }
        h1 {
            font-size: 28px;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #22d3ee, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            color: #94a3b8;
            margin-bottom: 24px;
        }
        .btn {
            display: inline-block;
            background: linear-gradient(135deg, #22d3ee, #10b981);
            color: #0f172a;
            padding: 12px 32px;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            margin-top: 16px;
        }
        .api-info {
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid #334155;
            text-align: left;
        }
        .api-info h3 {
            font-size: 14px;
            color: #94a3b8;
            margin-bottom: 12px;
        }
        .endpoint {
            font-family: monospace;
            font-size: 13px;
            padding: 8px 12px;
            background: #0f172a;
            border-radius: 4px;
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="logo">🔥</div>
            <h1>Welcome to MoMo</h1>
            <p class="subtitle">Modular Offensive Mobile Operations</p>
            
            <p>The wizard frontend is not installed.<br>
               Use the API endpoints below or install the React frontend.</p>
            
            <a href="/api/docs" class="btn">Open API Docs</a>
            
            <div class="api-info">
                <h3>Quick API Endpoints</h3>
                <div class="endpoint">GET /api/status</div>
                <div class="endpoint">POST /api/step/language</div>
                <div class="endpoint">POST /api/step/password</div>
                <div class="endpoint">GET /api/wifi/scan</div>
                <div class="endpoint">POST /api/step/network</div>
                <div class="endpoint">POST /api/step/profile</div>
                <div class="endpoint">GET /api/nexus/discover</div>
                <div class="endpoint">POST /api/complete</div>
            </div>
        </div>
    </div>
</body>
</html>
"""


def create_wizard_app(
    network_manager=None,
    nexus_discovery=None,
    config_generator=None,
    static_dir: Optional[Path] = None,
) -> FastAPI:
    """
    Factory function to create the wizard FastAPI app.
    
    Args:
        network_manager: NetworkManager instance
        nexus_discovery: NexusDiscovery instance
        config_generator: ConfigGenerator instance
        static_dir: Path to static files
        
    Returns:
        Configured FastAPI application
    """
    server = WizardServer(
        network_manager=network_manager,
        nexus_discovery=nexus_discovery,
        config_generator=config_generator,
        static_dir=static_dir,
    )
    return server.app

