from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from src.backend.auth_routes import router as auth_router

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class HealthResponse(BaseModel):
    status: str
    service: str


def create_app(container=None) -> FastAPI:
    """Create the backend FastAPI app.

    Without ``container``, only ``/health`` is available (import/smoke-safe).
    With a wired container, auth routes are mounted.
    """
    app = FastAPI(title="QMTool Backend")
    app.state.container = container

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next: Callable) -> Response:
        header_value = request.headers.get("X-Request-ID")
        if header_value and _REQUEST_ID_RE.fullmatch(header_value.strip()):
            request_id = header_value.strip()
        else:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health", response_model=HealthResponse)
    def _health() -> HealthResponse:
        return HealthResponse(status="ok", service="qmtool-backend")

    if container is not None:
        app.include_router(auth_router)

    return app
