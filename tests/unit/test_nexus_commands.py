"""
Tests for Nexus Command Listener and Offline Queue.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from momo.infrastructure.nexus.command_listener import (
    CommandStatus,
    NexusCommandListener,
    ReceivedCommand,
)
from momo.infrastructure.nexus.offline_queue import (
    OfflineQueue,
    QueueItem,
    QueueItemType,
    QueueItemStatus,
    QueueSyncer,
)


# =============================================================================
# Command Listener Tests
# =============================================================================

class TestReceivedCommand:
    """Tests for ReceivedCommand dataclass."""
    
    def test_create_command(self):
        """Test creating a received command."""
        cmd = ReceivedCommand(
            id="cmd-001",
            name="scan",
            params={"target": "TestNetwork"},
            timeout=60,
        )
        
        assert cmd.id == "cmd-001"
        assert cmd.name == "scan"
        assert cmd.params == {"target": "TestNetwork"}
        assert cmd.timeout == 60
        assert cmd.status == CommandStatus.PENDING
    
    def test_command_defaults(self):
        """Test command default values."""
        cmd = ReceivedCommand(id="cmd-002", name="ping")
        
        assert cmd.params == {}
        assert cmd.timeout == 30
        assert cmd.status == CommandStatus.PENDING
        assert cmd.result is None


class TestNexusCommandListener:
    """Tests for NexusCommandListener."""
    
    def test_init(self):
        """Test listener initialization."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        assert listener.device_id == "momo-001"
        assert listener.nexus_url == "http://nexus.local:8080"
        assert listener.use_websocket is True
        assert "ping" in listener._handlers
    
    def test_register_handler(self):
        """Test registering a command handler."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        async def handle_scan(params):
            return {"scanned": True}
        
        listener.register_handler("scan", handle_scan)
        
        assert "scan" in listener._handlers
        assert listener._handlers["scan"] == handle_scan
    
    def test_unregister_handler(self):
        """Test unregistering a command handler."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        async def handle_scan(params):
            return {"scanned": True}
        
        listener.register_handler("scan", handle_scan)
        assert "scan" in listener._handlers
        
        listener.unregister_handler("scan")
        assert "scan" not in listener._handlers
    
    @pytest.mark.asyncio
    async def test_builtin_ping_handler(self):
        """Test built-in ping handler."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        result = await listener._handle_ping({})
        
        assert result["pong"] is True
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        """Test successful command execution."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        # Mock session for reporting
        listener._session = MagicMock()
        listener._session.post = AsyncMock()
        
        async def handle_test(params):
            return {"success": True, "value": params.get("x", 0) * 2}
        
        listener.register_handler("test", handle_test)
        
        cmd = ReceivedCommand(id="cmd-001", name="test", params={"x": 5})
        
        with patch.object(listener, "_report_result", new_callable=AsyncMock):
            await listener._execute_command(cmd)
        
        assert cmd.status == CommandStatus.SUCCESS
        assert cmd.result == {"success": True, "value": 10}
    
    @pytest.mark.asyncio
    async def test_execute_command_unknown(self):
        """Test executing unknown command."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        listener._session = MagicMock()
        
        cmd = ReceivedCommand(id="cmd-001", name="unknown_command")
        
        with patch.object(listener, "_report_result", new_callable=AsyncMock) as mock_report:
            await listener._execute_command(cmd)
            
            mock_report.assert_called_once()
            # Check that success=False was passed
            _, kwargs = mock_report.call_args
            assert kwargs.get("success") is False or mock_report.call_args[0][1] is False
            assert "Unknown command" in str(mock_report.call_args)
    
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self):
        """Test command timeout handling."""
        listener = NexusCommandListener(
            nexus_url="http://nexus.local:8080",
            device_id="momo-001",
            api_key="test-key",
        )
        
        listener._session = MagicMock()
        
        async def slow_handler(params):
            await asyncio.sleep(10)
            return {"done": True}
        
        listener.register_handler("slow", slow_handler)
        
        cmd = ReceivedCommand(id="cmd-001", name="slow", timeout=1)
        
        with patch.object(listener, "_report_result", new_callable=AsyncMock):
            await listener._execute_command(cmd)
        
        assert cmd.status == CommandStatus.TIMEOUT


# =============================================================================
# Offline Queue Tests
# =============================================================================

class TestOfflineQueue:
    """Tests for OfflineQueue."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_queue.db"
    
    @pytest.mark.asyncio
    async def test_init_and_close(self, temp_db):
        """Test queue initialization and closing."""
        queue = OfflineQueue(temp_db)
        await queue.initialize()
        
        assert queue._conn is not None
        assert temp_db.exists()
        
        await queue.close()
        assert queue._conn is None
    
    @pytest.mark.asyncio
    async def test_enqueue_handshake(self, temp_db):
        """Test enqueueing a handshake."""
        async with OfflineQueue(temp_db) as queue:
            item_id = await queue.enqueue(
                QueueItemType.HANDSHAKE,
                {"ssid": "TestNetwork", "bssid": "AA:BB:CC:DD:EE:FF", "channel": 6}
            )
            
            assert item_id > 0
            
            items = await queue.get_pending()
            assert len(items) == 1
            assert items[0].item_type == QueueItemType.HANDSHAKE
            assert items[0].data["ssid"] == "TestNetwork"
    
    @pytest.mark.asyncio
    async def test_enqueue_credential(self, temp_db):
        """Test enqueueing a credential."""
        async with OfflineQueue(temp_db) as queue:
            item_id = await queue.enqueue_credential(
                ssid="FakeAP",
                client_mac="11:22:33:44:55:66",
                username="user@example.com",
                password="secret123",
            )
            
            assert item_id > 0
            
            item = await queue.get_item(item_id)
            assert item is not None
            assert item.data["username"] == "user@example.com"
    
    @pytest.mark.asyncio
    async def test_enqueue_status_replaces_pending(self, temp_db):
        """Test that status updates replace existing pending status."""
        async with OfflineQueue(temp_db) as queue:
            await queue.enqueue_status(battery=90, temperature=45)
            await queue.enqueue_status(battery=85, temperature=50)
            await queue.enqueue_status(battery=80, temperature=55)
            
            items = await queue.get_pending()
            status_items = [i for i in items if i.item_type == QueueItemType.STATUS]
            
            # Should only have 1 status (latest)
            assert len(status_items) == 1
            assert status_items[0].data["battery"] == 80
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, temp_db):
        """Test that items are ordered by priority."""
        async with OfflineQueue(temp_db) as queue:
            # Add in reverse priority order
            await queue.enqueue(QueueItemType.STATUS, {"battery": 90})
            await queue.enqueue(QueueItemType.LOOT, {"name": "data.txt"})
            await queue.enqueue(QueueItemType.HANDSHAKE, {"ssid": "Target"})
            
            items = await queue.get_pending()
            
            # Handshake should be first (priority 1)
            assert items[0].item_type == QueueItemType.HANDSHAKE
    
    @pytest.mark.asyncio
    async def test_mark_sent(self, temp_db):
        """Test marking item as sent removes it."""
        async with OfflineQueue(temp_db) as queue:
            item_id = await queue.enqueue(
                QueueItemType.HANDSHAKE,
                {"ssid": "Test"}
            )
            
            await queue.mark_sent(item_id)
            
            item = await queue.get_item(item_id)
            assert item is None
    
    @pytest.mark.asyncio
    async def test_mark_failed_increments_retries(self, temp_db):
        """Test that marking failed increments retry count."""
        async with OfflineQueue(temp_db) as queue:
            item_id = await queue.enqueue(
                QueueItemType.HANDSHAKE,
                {"ssid": "Test"}
            )
            
            await queue.mark_failed(item_id, "Connection timeout")
            
            item = await queue.get_item(item_id)
            assert item.retries == 1
            assert item.last_error == "Connection timeout"
    
    @pytest.mark.asyncio
    async def test_max_retries_excludes_from_pending(self, temp_db):
        """Test that items exceeding max retries are excluded."""
        async with OfflineQueue(temp_db, max_retries=3) as queue:
            item_id = await queue.enqueue(
                QueueItemType.HANDSHAKE,
                {"ssid": "Test"}
            )
            
            # Fail 3 times
            for _ in range(3):
                await queue.mark_failed(item_id, "Error")
            
            items = await queue.get_pending()
            assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_get_stats(self, temp_db):
        """Test getting queue statistics."""
        async with OfflineQueue(temp_db) as queue:
            await queue.enqueue(QueueItemType.HANDSHAKE, {"ssid": "Test1"})
            await queue.enqueue(QueueItemType.HANDSHAKE, {"ssid": "Test2"})
            await queue.enqueue(QueueItemType.CREDENTIAL, {"ssid": "Test3"})
            
            stats = await queue.get_stats()
            
            assert stats["total"] == 3
            assert stats["pending"] == 3
            assert stats["sending"] == 0
    
    @pytest.mark.asyncio
    async def test_clear_all(self, temp_db):
        """Test clearing entire queue."""
        async with OfflineQueue(temp_db) as queue:
            await queue.enqueue(QueueItemType.HANDSHAKE, {"ssid": "Test1"})
            await queue.enqueue(QueueItemType.HANDSHAKE, {"ssid": "Test2"})
            
            count = await queue.clear_all()
            assert count == 2
            
            items = await queue.get_pending()
            assert len(items) == 0


# =============================================================================
# Queue Syncer Tests
# =============================================================================

class TestQueueSyncer:
    """Tests for QueueSyncer."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_queue.db"
    
    @pytest.mark.asyncio
    async def test_syncer_processes_items(self, temp_db):
        """Test that syncer processes queued items."""
        async with OfflineQueue(temp_db) as queue:
            # Add test items
            await queue.enqueue(QueueItemType.HANDSHAKE, {
                "ssid": "Target",
                "bssid": "AA:BB:CC:DD:EE:FF",
                "channel": 6,
            })
            
            # Mock Nexus client
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.upload_handshake = AsyncMock(return_value={"id": "hs-001"})
            
            syncer = QueueSyncer(queue, mock_client, sync_interval=0.1)
            
            # Process one batch
            await syncer._process_batch()
            
            # Verify item was sent
            mock_client.upload_handshake.assert_called_once()
            
            # Verify queue is empty
            items = await queue.get_pending()
            assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_syncer_handles_failure(self, temp_db):
        """Test that syncer handles sync failures."""
        async with OfflineQueue(temp_db) as queue:
            await queue.enqueue(QueueItemType.HANDSHAKE, {
                "ssid": "Target",
                "bssid": "AA:BB:CC:DD:EE:FF",
                "channel": 6,
            })
            
            # Mock Nexus client that fails
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.upload_handshake = AsyncMock(side_effect=Exception("Network error"))
            
            syncer = QueueSyncer(queue, mock_client, sync_interval=0.1)
            
            await syncer._process_batch()
            
            # Item should still be in queue with retry incremented
            items = await queue.get_pending()
            assert len(items) == 1
            assert items[0].retries == 1

