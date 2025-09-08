from momo.apps.momo_core.bettercap import build_bettercap_args
from momo.config import BettercapConfig, MomoConfig


def test_bettercap_args_passive():
    cfg = MomoConfig()
    cfg.interface.name = "wlan1"
    cfg.bettercap = BettercapConfig(enabled=True, allow_assoc=False, allow_deauth=False)
    args = build_bettercap_args(cfg)
    assert "bettercap" in args[0]
    assert "-iface" in args and "wlan1" in args
    assert "wifi.assoc on" not in " ".join(args)
    assert "wifi.deauth on" not in " ".join(args)


def test_bettercap_args_aggressive():
    cfg = MomoConfig()
    cfg.interface.name = "wlan1"
    cfg.bettercap = BettercapConfig(enabled=True, allow_assoc=True, allow_deauth=True)
    args = build_bettercap_args(cfg)
    s = " ".join(args)
    assert "wifi.assoc on" in s
    assert "wifi.deauth on" in s


