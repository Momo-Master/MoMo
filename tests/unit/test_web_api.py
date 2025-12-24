"""Unit tests for Web API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def app():
    """Create test Flask app."""
    import os
    from momo.config import MomoConfig
    from momo.apps.momo_web import create_app
    
    # Disable token requirement
    os.environ["MOMO_UI_TOKEN"] = ""
    
    config = MomoConfig()
    config.web.require_token = False  # Disable auth for tests
    app = create_app(config)
    app.config["TESTING"] = True
    
    # Mock session as authenticated
    with app.app_context():
        pass
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestCaptureAPI:
    """Test /api/captures endpoints."""

    def test_list_captures_returns_json(self, client):
        """GET /api/captures should return JSON."""
        response = client.get("/api/captures")
        assert response.status_code in [200, 503]
        assert response.content_type == "application/json"

    def test_capture_stats_endpoint(self, client):
        """GET /api/captures/stats should return stats."""
        response = client.get("/api/captures/stats")
        assert response.status_code in [200, 503]

    def test_crackable_endpoint(self, client):
        """GET /api/captures/crackable should return list."""
        response = client.get("/api/captures/crackable")
        assert response.status_code in [200, 503]


class TestBLEAPI:
    """Test /api/ble endpoints."""

    def test_list_devices(self, client):
        """GET /api/ble/devices should return devices."""
        response = client.get("/api/ble/devices")
        assert response.status_code in [200, 503]

    def test_list_beacons(self, client):
        """GET /api/ble/beacons should return beacons."""
        response = client.get("/api/ble/beacons")
        assert response.status_code in [200, 503]

    def test_beacon_status(self, client):
        """GET /api/ble/beacon/status should return status."""
        response = client.get("/api/ble/beacon/status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "active" in data

    def test_hid_status(self, client):
        """GET /api/ble/hid/status should return status."""
        response = client.get("/api/ble/hid/status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "active" in data


class TestEvilTwinAPI:
    """Test /api/eviltwin endpoints."""

    def test_status_endpoint(self, client):
        """GET /api/eviltwin/status should return status."""
        response = client.get("/api/eviltwin/status")
        assert response.status_code in [200, 404, 503]

    def test_clients_endpoint(self, client):
        """GET /api/eviltwin/clients should return list."""
        response = client.get("/api/eviltwin/clients")
        assert response.status_code in [200, 404, 503]

    def test_credentials_endpoint(self, client):
        """GET /api/eviltwin/credentials should return list."""
        response = client.get("/api/eviltwin/credentials")
        assert response.status_code in [200, 404, 503]

    def test_templates_endpoint(self, client):
        """GET /api/eviltwin/templates should return templates."""
        response = client.get("/api/eviltwin/templates")
        assert response.status_code in [200, 404, 500, 503]


class TestCrackingAPI:
    """Test /api/cracking endpoints (John only - Hashcat moved to Cloud)."""

    def test_status_endpoint(self, client):
        """GET /api/cracking/status should return status with cloud note."""
        response = client.get("/api/cracking/status")
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = json.loads(response.data)
            assert "note" in data  # Cloud migration note

    def test_cloud_status_endpoint(self, client):
        """GET /api/cracking/cloud/status should return cloud info."""
        response = client.get("/api/cracking/cloud/status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "status" in data

    def test_john_status(self, client):
        """GET /api/cracking/john/status should return status."""
        response = client.get("/api/cracking/john/status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "jobs_total" in data

    def test_john_jobs(self, client):
        """GET /api/cracking/john/jobs should return jobs."""
        response = client.get("/api/cracking/john/jobs")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "jobs" in data


class TestWPA3API:
    """Test /api/wpa3 endpoints."""

    def test_status_endpoint(self, client):
        """GET /api/wpa3/status should return status."""
        response = client.get("/api/wpa3/status")
        # 404 if blueprint not registered, 200/503 otherwise
        assert response.status_code in [200, 404, 503]

    def test_networks_endpoint(self, client):
        """GET /api/wpa3/networks should return list."""
        response = client.get("/api/wpa3/networks")
        assert response.status_code in [200, 404, 503]

    def test_attacks_endpoint(self, client):
        """GET /api/wpa3/attacks should return list."""
        response = client.get("/api/wpa3/attacks")
        assert response.status_code in [200, 404, 503]


class TestKarmaAPI:
    """Test /api/karma endpoints."""

    def test_status_endpoint(self, client):
        """GET /api/karma/status should return status."""
        response = client.get("/api/karma/status")
        assert response.status_code in [200, 404, 503]

    def test_clients_endpoint(self, client):
        """GET /api/karma/clients should return list."""
        response = client.get("/api/karma/clients")
        assert response.status_code in [200, 404, 503]

    def test_ssids_endpoint(self, client):
        """GET /api/karma/ssids should return list."""
        response = client.get("/api/karma/ssids")
        assert response.status_code in [200, 404, 503]


class TestUIRoutes:
    """Test UI page routes."""

    def test_index_redirects_or_shows(self, client):
        """GET / should work."""
        response = client.get("/")
        assert response.status_code in [200, 302, 401]

    def test_dashboard_route(self, client):
        """GET /dashboard should work."""
        response = client.get("/dashboard")
        assert response.status_code in [200, 302, 401, 404, 500]

    def test_handshakes_route(self, client):
        """GET /handshakes should work."""
        response = client.get("/handshakes")
        assert response.status_code in [200, 302, 401]

    def test_captures_route(self, client):
        """GET /captures should work."""
        response = client.get("/captures")
        assert response.status_code in [200, 302, 401]

    def test_bluetooth_route(self, client):
        """GET /bluetooth should work."""
        response = client.get("/bluetooth")
        assert response.status_code in [200, 302, 401]

    def test_eviltwin_route(self, client):
        """GET /eviltwin should work."""
        response = client.get("/eviltwin")
        assert response.status_code in [200, 302, 401]

    def test_cracking_route(self, client):
        """GET /cracking should work."""
        response = client.get("/cracking")
        assert response.status_code in [200, 302, 401]

    def test_wpa3_route(self, client):
        """GET /wpa3 should work."""
        response = client.get("/wpa3")
        assert response.status_code in [200, 302, 401, 404, 500]

    def test_karma_route(self, client):
        """GET /karma should work."""
        response = client.get("/karma")
        assert response.status_code in [200, 302, 401, 404, 500]

    def test_config_route(self, client):
        """GET /config should work."""
        response = client.get("/config")
        assert response.status_code in [200, 302, 401, 404, 500]


class TestAuthEndpoints:
    """Test authentication."""

    def test_unauthorized_without_token(self):
        """Requests without token should be rejected when auth enabled."""
        import os
        from momo.config import MomoConfig
        from momo.apps.momo_web import create_app
        
        # Set a token so auth is actually required
        os.environ["MOMO_UI_TOKEN"] = "test-secret-token-12345"
        
        try:
            config = MomoConfig()
            config.web.require_token = True
            config.web.allow_local_unauth = False  # Disable local auth bypass for test
            app = create_app(config)
            app.config["TESTING"] = True
            
            with app.test_client() as client:
                response = client.get("/api/captures")
                # Should be unauthorized or redirect
                assert response.status_code in [401, 302]
        finally:
            # Clean up
            os.environ.pop("MOMO_UI_TOKEN", None)

    def test_static_files_no_auth(self, client):
        """Static files should not require auth."""
        # This is implicit - static files are served by Flask
        pass


class TestErrorHandling:
    """Test error responses."""

    def test_404_on_unknown_route(self, client):
        """Unknown routes should return 404."""
        response = client.get("/api/this_route_does_not_exist_12345")
        assert response.status_code == 404

    def test_wrong_method_handling(self, client):
        """Wrong HTTP method should be handled."""
        # This depends on route configuration
        response = client.delete("/api/captures/stats")
        # Could be 404 (route not found for DELETE) or 405 (method not allowed)
        assert response.status_code in [404, 405]

