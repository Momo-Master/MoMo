from click.testing import CliRunner

from momo.cli import cli


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["version"], prog_name="momo")
    assert result.exit_code == 0
    assert "momo" in result.stdout


def test_init_creates_directories(tmp_path):
    runner = CliRunner()
    target = tmp_path / "momo_struct"
    result = runner.invoke(cli, ["init", str(target)], prog_name="momo")
    assert result.exit_code == 0
    assert (target / "apps" / "momo_core").exists()
    assert (target / "tools").exists()


def test_web_url_shows_urls_and_token(tmp_path):
    runner = CliRunner()
    token_path = tmp_path / ".momo_ui_token"
    token_path.write_text("tokentest", encoding="utf-8")
    # Monkeypatch the expected token file path by creating a symlink if possible or copying
    opt_token = Path("/opt/momo/.momo_ui_token")
    opt_token.parent.mkdir(parents=True, exist_ok=True)
    try:
        if opt_token.exists():
            opt_token.unlink()
    except Exception:
        pass
    try:
        opt_token.symlink_to(token_path)
    except Exception:
        opt_token.write_text("tokentest", encoding="utf-8")
    result = runner.invoke(cli, ["web-url", "--show-token"], prog_name="momo")
    assert result.exit_code == 0
    assert "Token" in result.stdout

