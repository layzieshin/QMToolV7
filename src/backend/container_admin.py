"""Static local-only administration blueprint for the Container demo host."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


router = APIRouter(prefix="/container/admin", include_in_schema=False)
_ASSET_ROOT = Path(__file__).resolve().parent / "static" / "container_admin"


def _asset(name: str) -> bytes:
    return (_ASSET_ROOT / name).read_bytes()


@router.get("", response_class=HTMLResponse)
def admin_builder() -> HTMLResponse:
    return HTMLResponse(_asset("index.html"))


@router.get("/app.css")
def admin_styles() -> Response:
    return Response(_asset("app.css"), media_type="text/css; charset=utf-8")


@router.get("/app.js")
def admin_script() -> Response:
    return Response(_asset("app.js"), media_type="text/javascript; charset=utf-8")
