from __future__ import annotations

from pydantic import BaseModel

from fastapi import FastAPI


class HealthResponse(BaseModel):
    status: str
    service: str


def create_app() -> FastAPI:
    app = FastAPI(title="QMTool Backend")

    @app.get("/health", response_model=HealthResponse)
    def _health() -> HealthResponse:
        return HealthResponse(status="ok", service="qmtool-backend")

    return app
