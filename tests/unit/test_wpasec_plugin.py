import time

import momo.apps.momo_plugins.wpa_sec as wp


def test_wpasec_dryrun_without_key(monkeypatch, tmp_path):
    cfg = {
        "upload": True,
        "queue_dir": str(tmp_path),
        "retry_secs": 0,
        "dry_run": True,
    }
    (tmp_path / "test.22000").write_text("dummy", encoding="utf-8")
    wp.init(cfg)
    time.sleep(0.05)
    m = wp.get_metrics()
    assert m["momo_wpasec_submissions_total"]["dryrun"] >= 0

