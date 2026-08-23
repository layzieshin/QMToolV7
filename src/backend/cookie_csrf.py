"""Cookie session and CSRF double-submit helpers (WEB00 transport only)."""
from __future__ import annotations

import secrets
from typing import Final

from fastapi import Request, Response

SESSION_COOKIE_NAME: Final[str] = "qmtool_session"
CSRF_COOKIE_NAME: Final[str] = "qmtool_csrf"
CSRF_HEADER_NAME: Final[str] = "X-CSRF-Token"

SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})

# Mutations exempt from CSRF when using cookie auth (CLI token issuance).
CSRF_EXEMPT_PATHS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("POST", "/api/v1/auth/token"),
    }
)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _cookie_kwargs(*, httponly: bool) -> dict[str, str | bool]:
    return {
        "httponly": httponly,
        "secure": True,
        "samesite": "lax",
        "path": "/",
    }


def set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(SESSION_COOKIE_NAME, raw_token, **_cookie_kwargs(httponly=True))


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(CSRF_COOKIE_NAME, csrf_token, **_cookie_kwargs(httponly=False))


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=False,
        samesite="lax",
    )


def read_csrf_cookie(request: Request) -> str | None:
    value = request.cookies.get(CSRF_COOKIE_NAME)
    return value if value else None


def csrf_header_matches(request: Request) -> bool:
    cookie_value = read_csrf_cookie(request)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value:
        return False
    return secrets.compare_digest(cookie_value, header_value)


def authorization_header_present(request: Request) -> bool:
    auth = request.headers.get("Authorization")
    return bool(auth and auth.strip())
