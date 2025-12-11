"""Integration tests for the Plugin System."""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_full_plugin_lifecycle():
    """Test complete plugin lifecycle."""
    from momo.core.plugin import PluginManager, get_plugin_manager
    from momo.plugins.example_plugin import ExamplePlugin

    # Get manager
    manager = get_plugin_manager()
    manager._plugins.clear()
    manager._plugin_classes.clear()
    manager._load_order.clear()

    # Create and register
    plugin = ExamplePlugin()
    manager.register(plugin)

    assert plugin.name == "example"
    assert plugin.state.value == "loaded"

    # Start
    result = await manager.start_plugin("example", {"interval": 1})
    assert result is True
    assert plugin.is_running is True
    assert plugin.state.value == "running"

    # Check status
    status = plugin.get_status()
    assert status["name"] == "example"
    assert status["version"] == "1.0.0"
    assert status["state"] == "running"

    # Metrics
    plugin.increment_metric("test_runs")
    metrics = plugin.get_metrics()
    assert "momo_example_test_runs" in metrics
    assert metrics["momo_example_test_runs"] == 1

    # Stop
    await manager.stop_plugin("example")
    assert plugin.state.value == "stopped"
    assert plugin.is_running is False


@pytest.mark.asyncio
async def test_plugin_event_communication():
    """Test plugins communicating via events."""
    from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

    received = []

    class Sender(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="sender_test")

        async def on_start(self):
            await self.emit("ping", {"data": 123})

    class Receiver(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="receiver_test")

        def on_load(self):
            self.on("sender_test.ping", lambda d: received.append(d))

    manager = PluginManager()
    manager._plugins.clear()

    receiver = Receiver()
    sender = Sender()

    manager.register(receiver)
    manager.register(sender)

    await manager.start_plugin("receiver_test")
    await manager.start_plugin("sender_test")

    await asyncio.sleep(0.01)

    assert len(received) == 1
    assert received[0]["data"] == 123

    await manager.stop_all()


@pytest.mark.asyncio
async def test_plugin_dependency_check():
    """Test plugin dependency validation."""
    from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

    class DependentPlugin(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(
                name="dependent",
                requires=["nonexistent_plugin"],
            )

    manager = PluginManager()
    manager._plugins.clear()

    plugin = DependentPlugin()
    manager.register(plugin)

    # Should fail because dependency not met
    result = await manager.start_plugin("dependent")
    assert result is False


@pytest.mark.asyncio
async def test_manager_start_stop_all():
    """Test starting and stopping all plugins."""
    from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

    starts = []
    stops = []

    class Plugin1(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="p1", priority=10)

        async def on_start(self):
            starts.append("p1")

        async def on_stop(self):
            stops.append("p1")

    class Plugin2(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="p2", priority=20)

        async def on_start(self):
            starts.append("p2")

        async def on_stop(self):
            stops.append("p2")

    manager = PluginManager()
    manager._plugins.clear()
    manager._load_order.clear()

    manager.register(Plugin1())
    manager.register(Plugin2())

    # Start all (should be in priority order)
    count = await manager.start_all()
    assert count == 2
    assert starts == ["p1", "p2"]  # p1 has lower priority, starts first

    # Stop all (should be in reverse order)
    await manager.stop_all()
    assert stops == ["p2", "p1"]  # Reverse order


@pytest.mark.asyncio
async def test_plugin_get_other_plugin():
    """Test plugin accessing another plugin."""
    from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

    class HelperPlugin(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="helper")

        def get_value(self):
            return 42

    class MainPlugin(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="main")

        async def on_start(self):
            helper = self.get_plugin("helper")
            if helper:
                self.helper_value = helper.get_value()

    manager = PluginManager()
    manager._plugins.clear()

    helper = HelperPlugin()
    main = MainPlugin()

    manager.register(helper)
    manager.register(main)

    await manager.start_plugin("helper")
    await manager.start_plugin("main")

    assert hasattr(main, "helper_value")
    assert main.helper_value == 42

    await manager.stop_all()


@pytest.mark.asyncio
async def test_manager_metrics_aggregation():
    """Test aggregating metrics from all plugins."""
    from momo.core.plugin import BasePlugin, PluginManager, PluginMetadata

    class P1(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="m1")

    class P2(BasePlugin):
        @staticmethod
        def metadata():
            return PluginMetadata(name="m2")

    manager = PluginManager()
    manager._plugins.clear()

    p1 = P1()
    p2 = P2()

    manager.register(p1)
    manager.register(p2)

    p1.increment_metric("runs", 10)
    p2.increment_metric("runs", 5)
    p2.increment_metric("errors", 2)

    metrics = manager.get_all_metrics()

    assert metrics["momo_m1_runs"] == 10
    assert metrics["momo_m2_runs"] == 5
    assert metrics["momo_m2_errors"] == 2

