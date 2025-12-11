"""Unit tests for the new Plugin System."""

from __future__ import annotations

import pytest


class TestPluginMetadata:
    """Test PluginMetadata."""

    def test_metadata_creation(self):
        """Metadata should be created with defaults."""
        from momo.core.plugin import PluginMetadata, PluginType

        meta = PluginMetadata(name="test_plugin")

        assert meta.name == "test_plugin"
        assert meta.version == "1.0.0"
        assert meta.priority == 100
        assert meta.plugin_type == PluginType.CUSTOM

    def test_metadata_to_dict(self):
        """Metadata should serialize."""
        from momo.core.plugin import PluginMetadata

        meta = PluginMetadata(
            name="test",
            version="2.0.0",
            author="Test Author",
        )
        data = meta.to_dict()

        assert data["name"] == "test"
        assert data["version"] == "2.0.0"
        assert data["author"] == "Test Author"


class TestPluginState:
    """Test PluginState enum."""

    def test_states(self):
        """All states should be defined."""
        from momo.core.plugin import PluginState

        assert PluginState.UNLOADED.value == "unloaded"
        assert PluginState.RUNNING.value == "running"
        assert PluginState.STOPPED.value == "stopped"
        assert PluginState.ERROR.value == "error"


class TestPluginType:
    """Test PluginType enum."""

    def test_types(self):
        """All types should be defined."""
        from momo.core.plugin import PluginType

        assert PluginType.CORE.value == "core"
        assert PluginType.SCANNER.value == "scanner"
        assert PluginType.ATTACK.value == "attack"
        assert PluginType.CUSTOM.value == "custom"


class TestBasePlugin:
    """Test BasePlugin class."""

    def test_plugin_creation(self):
        """Plugin should be created."""
        from momo.core.plugin import BasePlugin, PluginMetadata, PluginState

        class TestPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="test")

        plugin = TestPlugin()
        assert plugin.name == "test"
        assert plugin.state == PluginState.UNLOADED
        assert plugin.is_running is False

    def test_plugin_metrics(self):
        """Plugin should track metrics."""
        from momo.core.plugin import BasePlugin, PluginMetadata

        class TestPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="metric_test")

        plugin = TestPlugin()
        plugin.increment_metric("runs")
        plugin.increment_metric("runs")
        plugin.increment_metric("errors")

        metrics = plugin.get_metrics()
        assert metrics["momo_metric_test_runs"] == 2
        assert metrics["momo_metric_test_errors"] == 1

    def test_plugin_status(self):
        """Plugin should return status."""
        from momo.core.plugin import BasePlugin, PluginMetadata

        class TestPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="status_test", version="1.2.3")

        plugin = TestPlugin()
        status = plugin.get_status()

        assert status["name"] == "status_test"
        assert status["version"] == "1.2.3"
        assert status["state"] == "unloaded"


@pytest.mark.asyncio
class TestPluginManager:
    """Test PluginManager."""

    async def test_manager_singleton(self):
        """Manager should be singleton."""
        from momo.core.plugin import PluginManager

        manager1 = PluginManager()
        manager2 = PluginManager()

        assert manager1 is manager2

    async def test_register_plugin(self):
        """Plugin should be registered."""
        from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

        class TestPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="register_test")

        # Get fresh manager for this test
        manager = PluginManager()
        manager._plugins.clear()  # Reset

        plugin = TestPlugin()
        manager.register(plugin)

        assert "register_test" in manager.list_loaded()
        assert manager.get_plugin("register_test") is plugin

    async def test_start_stop_plugin(self):
        """Plugin should start and stop."""
        from momo.core.plugin import (
            BasePlugin,
            PluginManager,
            PluginMetadata,
            PluginState,
        )

        class TestPlugin(BasePlugin):
            def __init__(self):
                super().__init__()
                self.started = False
                self.stopped = False

            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="lifecycle_test")

            async def on_start(self) -> None:
                self.started = True

            async def on_stop(self) -> None:
                self.stopped = True

        manager = PluginManager()
        manager._plugins.clear()

        plugin = TestPlugin()
        manager.register(plugin)

        # Start
        result = await manager.start_plugin("lifecycle_test")
        assert result is True
        assert plugin.started is True
        assert plugin.state == PluginState.RUNNING

        # Stop
        result = await manager.stop_plugin("lifecycle_test")
        assert result is True
        assert plugin.stopped is True
        assert plugin.state == PluginState.STOPPED

    async def test_plugin_events(self):
        """Plugins should communicate via events."""
        from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

        received_events = []

        class SenderPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="sender")

            async def on_start(self) -> None:
                await self.emit("hello", {"message": "world"})

        class ReceiverPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="receiver")

            def on_load(self) -> None:
                self.on("sender.hello", self._on_hello)

            def _on_hello(self, data):
                received_events.append(data)

        manager = PluginManager()
        manager._plugins.clear()

        receiver = ReceiverPlugin()
        sender = SenderPlugin()

        manager.register(receiver)
        manager.register(sender)

        await manager.start_plugin("receiver")
        await manager.start_plugin("sender")

        # Give time for event propagation
        import asyncio
        await asyncio.sleep(0.01)

        assert len(received_events) == 1
        assert received_events[0]["message"] == "world"

    async def test_get_all_metrics(self):
        """Manager should aggregate metrics."""
        from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

        class Plugin1(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="p1")

        class Plugin2(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(name="p2")

        manager = PluginManager()
        manager._plugins.clear()

        p1 = Plugin1()
        p2 = Plugin2()

        manager.register(p1)
        manager.register(p2)

        p1.increment_metric("runs", 5)
        p2.increment_metric("runs", 3)

        metrics = manager.get_all_metrics()

        assert metrics["momo_p1_runs"] == 5
        assert metrics["momo_p2_runs"] == 3


class TestExamplePlugin:
    """Test the example plugin."""

    def test_example_plugin_loads(self):
        """Example plugin should load."""
        from momo.plugins.example_plugin import ExamplePlugin

        plugin = ExamplePlugin()
        meta = plugin.metadata()

        assert meta.name == "example"
        assert meta.version == "1.0.0"

