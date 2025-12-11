from pathlib import Path

from momo.tools.storage_manager import enforce_quota


def _mk_day(base: Path, name: str, files: int = 1, size: int = 1024) -> None:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    for i in range(files):
        p = d / f"f{i}"
        p.write_bytes(b"x" * size)


def test_prune_by_days(tmp_path: Path):
    logs = tmp_path
    # make 35 days
    for i in range(35):
        _mk_day(logs, f"2025-01-{i+1:02d}")
    stats = enforce_quota(logs, max_days=30, max_bytes=10**12, low_space_bytes_threshold=0, enabled=True)
    # 5 pruned
    assert stats.pruned_days_total == 5
    # oldest remaining should be day 6
    assert (logs / "2025-01-06").exists()


def test_prune_by_size(tmp_path: Path):
    logs = tmp_path
    _mk_day(logs, "2025-01-01", files=2, size=1024 * 1024)
    _mk_day(logs, "2025-01-02", files=2, size=1024 * 1024)
    # tiny cap forces removal of oldest until under ~1MB
    stats = enforce_quota(logs, max_days=30, max_bytes=1024 * 1024, low_space_bytes_threshold=0, enabled=True)
    assert stats.pruned_days_total >= 1


def test_disabled_mode_no_delete(tmp_path: Path):
    logs = tmp_path
    _mk_day(logs, "2025-01-01")
    stats = enforce_quota(logs, max_days=1, max_bytes=1, low_space_bytes_threshold=0, enabled=False)
    assert (logs / "2025-01-01").exists()
    assert stats.total_bytes >= 0


def test_safety_skip_misc_and_symlink(tmp_path: Path):
    logs = tmp_path
    (logs / "misc").mkdir()
    _mk_day(logs, "2025-01-01")
    # create symlink pointing to day (should be ignored and day deleted directly)
    try:
        (logs / "link").symlink_to(logs / "2025-01-01")
    except Exception:
        pass
    enforce_quota(logs, max_days=0, max_bytes=0, low_space_bytes_threshold=0, enabled=True)
    assert not (logs / "2025-01-01").exists()
    assert (logs / "misc").exists()

