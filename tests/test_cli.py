from click.testing import CliRunner

from momo.cli import app


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "momo" in result.stdout


def test_init_creates_directories(tmp_path):
    runner = CliRunner()
    target = tmp_path / "momo_struct"
    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 0
    assert (target / "apps" / "momo_core").exists()
    assert (target / "tools").exists()


