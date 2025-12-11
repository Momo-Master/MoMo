from momo.config import resolve_config_path


def test_resolve_prefers_cli(tmp_path, monkeypatch):
    cfg = tmp_path / "a.yml"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MOMO_CONFIG", str(tmp_path / "b.yml"))
    p = resolve_config_path(cfg)
    assert p == cfg.resolve()


def test_resolve_env_when_no_cli(tmp_path, monkeypatch):
    cfg = tmp_path / "b.yml"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("MOMO_CONFIG", raising=False)
    monkeypatch.setenv("MOMO_CONFIG", str(cfg))
    p = resolve_config_path(None)
    assert p == cfg.resolve()

