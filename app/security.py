from __future__ import annotations

from functools import wraps
from urllib.parse import urlsplit

from flask import abort, redirect, request, session, url_for


def current_user() -> dict | None:
    return session.get("user")


def is_safe_relative_url(value: str | None) -> bool:
    if not value or len(value) > 500:
        return False
    parts = urlsplit(value)
    return not parts.scheme and not parts.netloc and value.startswith("/") and not value.startswith("//")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


def role_required(*allowed_roles: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            roles = set(current_user().get("roles", []))
            if not roles.intersection(allowed_roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
