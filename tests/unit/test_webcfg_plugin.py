import os

from momo.apps.momo_plugins import webcfg


def test_webcfg_refuses_without_token(monkeypatch):
    os.environ.pop("MOMO_UI_TOKEN", None)
    app = webcfg.get_app(allow_unauth=False)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code in {401, 429}


def test_webcfg_accepts_with_token(monkeypatch):
    os.environ["MOMO_UI_TOKEN"] = "tok"
    app = webcfg.get_app(allow_unauth=False)
    client = app.test_client()
    resp = client.get("/", headers={"Authorization": "Bearer tok"})
    assert resp.status_code in {200, 429}

