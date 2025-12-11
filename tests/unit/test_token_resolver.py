from __future__ import annotations

import os
from pathlib import Path

from momo.apps.momo_web.__init__ import _resolve_token


def test_token_resolver_prefers_env(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / ".momo_ui_token"
    token_file.write_text("filetoken", encoding="utf-8")
    monkeypatch.setenv("MOMO_UI_TOKEN", "envtoken")
    got = _resolve_token("MOMO_UI_TOKEN", token_file)
    assert got == "envtoken"


def test_token_resolver_reads_file_when_env_empty(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / ".momo_ui_token"
    token_file.write_text("filetoken", encoding="utf-8")
    monkeypatch.delenv("MOMO_UI_TOKEN", raising=False)
    got = _resolve_token("MOMO_UI_TOKEN", token_file)
    assert got == "filetoken"


def test_token_resolver_generates_when_missing(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / ".momo_ui_token"
    try:
        token_file.unlink()
    except FileNotFoundError:
        pass
    monkeypatch.delenv("MOMO_UI_TOKEN", raising=False)
    got = _resolve_token("MOMO_UI_TOKEN", token_file)
    assert isinstance(got, str) and len(got) >= 16
    # persisted
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8").strip() == got


