"""Enforce CSRF double-submit for cookie-authenticated API mutations (WEB00)."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from src.backend.cookie_csrf import (
    CSRF_EXEMPT_PATHS,
    SAFE_METHODS,
    SESSION_COOKIE_NAME,
    authorization_header_present,
    csrf_header_matches,
)


async def enforce_cookie_csrf(request: Request, call_next: Callable) -> Response:
    if request.method in SAFE_METHODS:
        return await call_next(request)
    if not request.url.path.startswith("/api/v1/"):
        return await call_next(request)
    if authorization_header_present(request):
        return await call_next(request)
    key = (request.method.upper(), request.url.path)
    if key in CSRF_EXEMPT_PATHS:
        return await call_next(request)

    # Browser login always requires CSRF double-submit (pre-session).
    if key == ("POST", "/api/v1/auth/login"):
        if not csrf_header_matches(request):
            return JSONResponse(
                status_code=403,
                content={"detail": {"error": "csrf_required", "message": "csrf token missing or invalid"}},
            )
        return await call_next(request)

    # Cookie-authenticated mutations require CSRF; unauthenticated calls pass through to auth.
    if request.cookies.get(SESSION_COOKIE_NAME):
        if not csrf_header_matches(request):
            return JSONResponse(
                status_code=403,
                content={"detail": {"error": "csrf_required", "message": "csrf token missing or invalid"}},
            )
    return await call_next(request)
