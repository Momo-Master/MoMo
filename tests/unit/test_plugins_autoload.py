from __future__ import annotations

from momo.apps.momo_plugins.registry import load_enabled_plugins


def test_plugins_autoload_dryrun():
    enabled = ["autobackup", "wpa-sec"]
    options = {"autobackup": {}, "wpa-sec": {}}
    loaded, shutdowns = load_enabled_plugins(enabled, options, global_cfg=None)
    assert set(loaded).issuperset({"autobackup", "wpa-sec"})
    for mod in shutdowns:
        assert hasattr(mod, "stop") or hasattr(mod, "shutdown")

