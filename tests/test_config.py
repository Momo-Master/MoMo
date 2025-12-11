from pathlib import Path

import pytest

from momo.config import MomoConfig, load_config


def test_default_model_has_expected_paths(tmp_path: Path):
    cfg = MomoConfig()
    assert cfg.logging.base_dir.as_posix() == "logs"
    assert cfg.handshakes_dir.as_posix().endswith("logs/handshakes")
    assert cfg.meta_dir.as_posix().endswith("logs/meta")


def test_yaml_loads_and_validates(tmp_path: Path):
    yml = tmp_path / "momo.yml"
    yml.write_text(
        """
mode: passive
interface:
  name: wlan1
logging:
  base_dir: logs
        """.strip(),
        encoding="utf-8",
    )
    cfg = load_config(yml)
    assert cfg.interface.name == "wlan1"


def test_invalid_channel_raises(tmp_path: Path):
    yml = tmp_path / "momo.yml"
    yml.write_text(
        """
interface:
  channels: [0, 1]
        """.strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(yml)


