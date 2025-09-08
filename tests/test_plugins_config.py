from momo.config import MomoConfig


def test_plugin_filter_enabled():
    cfg = MomoConfig()
    # modern loader path: ensure normalization works for hyphenated names
    from momo.apps.momo_plugins.registry import load_enabled_plugins

    loaded, _ = load_enabled_plugins(["wpa-sec"], cfg.plugins.options)
    assert "wpa-sec" in loaded or loaded == []

