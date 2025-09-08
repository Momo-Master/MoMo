from momo.apps.momo_plugins import PluginManager


def test_plugin_discovery_and_start():
    # Legacy discovery requires pwnagotchi example plugins; skip on missing deps
    import importlib
    try:
        importlib.import_module("momo.apps.momo_plugins.example_plugin")
    except Exception:
        return
    pm = PluginManager()
    pm.discover()
    assert pm.plugins is not None
    pm.start_all({})

