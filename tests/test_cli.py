from click.testing import CliRunner
from pathlib import Path

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
    result = runner.invoke(
        cli,
        ["web-url", "--show-token"],
        prog_name="momo",
        env={"MOMO_UI_TOKEN": "tokentest"},
    )
    assert result.exit_code == 0
    assert "tokentest" in result.stdout

