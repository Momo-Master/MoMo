from momo.config import MomoConfig
from momo.apps.momo_plugins import PluginManager


def test_plugin_filter_enabled():
    cfg = MomoConfig()
    cfg.plugins.example_plugin.enabled = True
    pm = PluginManager()
    pm.discover()
    pm.filter_enabled(cfg)
    assert pm.plugins is not None
    names = [name for name, _ in pm.plugins]
    assert "example_plugin" in names

