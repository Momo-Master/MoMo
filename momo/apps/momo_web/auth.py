from __future__ import annotations

import os
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import abort, current_app, request


def _get_env(name: str) -> str | None:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return None
    return val


def require_auth(token_env: str, password_env: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            bearer = request.headers.get("Authorization", "")
            basic = request.authorization
            token = _get_env(token_env)
            password = _get_env(password_env)
            if token is None and password is None:
                abort(401)
            if token and bearer.startswith("Bearer ") and bearer.split(" ", 1)[1] == token:
                return fn(*args, **kwargs)
            if password and basic and basic.username == "momo" and basic.password == password:
                return fn(*args, **kwargs)
            abort(401)

        return wrapper

    return decorator


def require_app_auth(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Auth decorator that reads config from current_app at request time."""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        cfg = current_app.config.get("MOMO_CONFIG")
        token_env = getattr(cfg.web.auth, "token_env", "MOMO_UI_TOKEN") if cfg else "MOMO_UI_TOKEN"
        password_env = getattr(cfg.web.auth, "password_env", "MOMO_UI_PASSWORD") if cfg else "MOMO_UI_PASSWORD"
        # Reuse logic from require_auth by evaluating dynamically
        bearer = request.headers.get("Authorization", "")
        basic = request.authorization
        token = _get_env(token_env)
        password = _get_env(password_env)
        if token is None and password is None:
            abort(401)
        if token and bearer.startswith("Bearer ") and bearer.split(" ", 1)[1] == token:
            return fn(*args, **kwargs)
        if password and basic and basic.username == "momo" and basic.password == password:
            return fn(*args, **kwargs)
        abort(401)

    return wrapper


