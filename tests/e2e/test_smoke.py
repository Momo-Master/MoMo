import subprocess

import pytest


@pytest.mark.e2e
def test_cli_version_runs():
    result = subprocess.run(["python", "-m", "momo.cli", "version"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "momo" in result.stdout


