from pathlib import Path

from momo.apps.momo_core.main import ensure_dirs
from momo.config import MomoConfig


def test_ensure_dirs(tmp_path: Path):
    cfg = MomoConfig()
    cfg.logging.base_dir = tmp_path
    ensure_dirs(cfg)
    day = next(tmp_path.iterdir())
    assert (day / cfg.capture.out_dir_name).exists()
    assert (day / cfg.capture.meta_dir_name).exists()


