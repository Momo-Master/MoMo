from __future__ import annotations

from momo.apps.momo_plugins import active_wifi as aw


def test_build_deauth_cmd_mdk4():
    cmd = aw._build_deauth_cmd("mdk4", "wlan0", "aa:bb:cc:dd:ee:ff", None, 50)
    assert cmd[:3] == ["mdk4", "wlan0", "d"]


def test_build_deauth_cmd_aireplay():
    cmd = aw._build_deauth_cmd("aireplay-ng", "wlan0", "aa:bb:cc:dd:ee:ff", None, 50)
    assert cmd[0:2] == ["aireplay-ng", "--deauth"]


