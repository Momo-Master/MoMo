from momo.apps.momo_plugins import PluginManager


def test_plugin_discovery_and_start():
    pm = PluginManager()
    pm.discover()
    assert pm.plugins is not None
    assert any(p.__class__.__name__ == "ExamplePlugin" for p in pm.plugins)
    pm.start_all({})

