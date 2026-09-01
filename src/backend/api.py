from __future__ import annotations

import os
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from fastapi.routing import APIRoute

from qm_platform.runtime.maintenance import is_maintenance_active
from src.backend.auth_routes import router as auth_router
from src.backend.cookie_csrf import SAFE_METHODS
from src.backend.csrf_middleware import enforce_cookie_csrf
from src.backend.documents_routes import router as documents_router
from src.backend.signature_routes import router as signature_router
from src.backend.user_admin_routes import router as user_admin_router

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class HealthResponse(BaseModel):
    status: str
    service: str


class ErrorDetail(BaseModel):
    error: str
    message: str
    current_etag: str | None = None
    current_state: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail | list[dict[str, Any]]


_ERROR_STATUS_CODES = (400, 401, 403, 404, 409, 413, 422, 501, 503)
_PRODUCTION_PROFILES = {"prod", "production"}

_API_V1 = "/api/v1"
_WEBCLIENT_DIST_ENV = "QMTOOL_WEBCLIENT_DIST"


def resolve_webclient_dist_dir() -> Path | None:
    """Return an existing webclient dist directory for same-origin static serving."""
    configured = os.environ.get(_WEBCLIENT_DIST_ENV, "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    home = os.environ.get("QMTOOL_HOME", "").strip()
    if home:
        candidates.append(Path(home) / "webclient" / "dist")

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        index_html = resolved / "index.html"
        if resolved.is_dir() and index_html.is_file():
            return resolved
    return None

# Documents mutations that always require If-Match at runtime (_required_if_match).
_DOCUMENTS_IF_MATCH_REQUIRED: frozenset[tuple[str, str]] = frozenset(
    {
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/assign-roles"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/start"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/editing-complete"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/review/accept"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/review/reject"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/approval/accept"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/approval/reject"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/abort"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/import-pdf"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/workflow/ensure-source-pdf"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/import-docx"),
        ("put", f"{_API_V1}/documents/headers/{{document_id}}"),
        ("patch", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/metadata"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/comments/sync-docx"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/comments"),
        ("post", f"{_API_V1}/documents/comments/{{comment_id}}/status"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/lifecycle/archive"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/lifecycle/extend-annual"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/lifecycle/new-version-after-archive"),
        ("post", f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/change-requests"),
    }
)
_DOCUMENTS_CREATE_FROM_TEMPLATE = (
    "post",
    f"{_API_V1}/documents/versions/{{document_id}}/{{version}}/create-from-template",
)
_DOCUMENTS_STATE_RESPONSE_SCHEMAS = frozenset(
    {"VersionStateResponse", "ExtendAnnualResponse", "EnsureSourcePdfResponse"}
)


def _stable_operation_id(route: APIRoute) -> str:
    path = re.sub(r"\{([^}]+)\}", r"by_\1", route.path.strip("/"))
    slug = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_").lower() or "root"
    method = sorted(route.methods or {"GET"})[0].lower()
    return f"{method}_{slug}"


def _error_response_schema() -> dict[str, Any]:
    return {
        "$ref": "#/components/schemas/ErrorResponse",
    }


def _add_header_parameter(
    operation: dict[str, Any],
    name: str,
    description: str,
    *,
    required: bool = False,
) -> None:
    parameters = operation.setdefault("parameters", [])
    for parameter in parameters:
        if parameter.get("name") == name and parameter.get("in") == "header":
            parameter["required"] = required
            parameter["description"] = description
            return
    parameters.append(
        {
            "name": name,
            "in": "header",
            "required": required,
            "description": description,
            "schema": {"type": "string"},
        }
    )


def _ensure_error_response(operation: dict[str, Any], status_code: str, description: str) -> None:
    operation.setdefault("responses", {})[status_code] = {
        "description": description,
        "content": {"application/json": {"schema": _error_response_schema()}},
    }


def _apply_if_match_contract(path: str, method: str, operation: dict[str, Any]) -> None:
    key = (method, path)
    if key in _DOCUMENTS_IF_MATCH_REQUIRED:
        _add_header_parameter(
            operation,
            "If-Match",
            "Required current document or resource ETag for optimistic mutation.",
            required=True,
        )
        _ensure_error_response(
            operation,
            "428",
            "Precondition required; If-Match header is missing.",
        )
        _ensure_error_response(
            operation,
            "409",
            "Optimistic-lock conflict; fetch current_state and current_etag.",
        )
        operation.setdefault("responses", {}).setdefault("200", {}).setdefault("headers", {})["ETag"] = {
            "description": "Current document version ETag.",
            "schema": {"type": "string"},
        }
        return
    if key == _DOCUMENTS_CREATE_FROM_TEMPLATE:
        _add_header_parameter(
            operation,
            "If-Match",
            (
                "Optional when the target version does not yet exist. "
                "Required (HTTP 428 when missing) if the target version already exists."
            ),
            required=False,
        )
        _ensure_error_response(
            operation,
            "428",
            "Precondition required when the target version already exists and If-Match is missing.",
        )
        _ensure_error_response(
            operation,
            "409",
            "Optimistic-lock conflict; fetch current_state and current_etag.",
        )
        operation.setdefault("responses", {}).setdefault("200", {}).setdefault("headers", {})["ETag"] = {
            "description": "Current document version ETag.",
            "schema": {"type": "string"},
        }
        operation["description"] = (
            "Create a document version from a template. If-Match is optional when the target "
            "version does not exist yet; when the target already exists, If-Match is mandatory "
            "and missing headers yield HTTP 428."
        )
        return
    # Strip accidental If-Match from non-contract documents mutations / reads.
    parameters = operation.get("parameters")
    if isinstance(parameters, list):
        operation["parameters"] = [
            parameter
            for parameter in parameters
            if not (parameter.get("name") == "If-Match" and parameter.get("in") == "header")
        ]


def _require_available_actions_on_state_responses(schema: dict[str, Any]) -> None:
    schemas = schema.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        return
    for name in _DOCUMENTS_STATE_RESPONSE_SCHEMAS:
        model = schemas.get(name)
        if not isinstance(model, dict):
            continue
        required = model.setdefault("required", [])
        if "available_actions" not in required:
            required.append("available_actions")
        properties = model.setdefault("properties", {})
        properties["available_actions"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Server-computed available_actions for the confirmed actor.",
        }


_OPENAPI_NO_SECURITY_PATHS = frozenset(
    {
        "/health",
        f"{_API_V1}/auth/csrf",
        f"{_API_V1}/auth/token",
    }
)
_BROWSER_LOGIN = ("post", f"{_API_V1}/auth/login")


def _apply_operation_security(path: str, method: str, operation: dict[str, Any]) -> None:
    if path in _OPENAPI_NO_SECURITY_PATHS:
        return
    if (method, path) == _BROWSER_LOGIN:
        operation["security"] = [{"CsrfHeader": []}]
        return
    if method.upper() in SAFE_METHODS:
        operation["security"] = [{"BearerAuth": []}, {"CookieSessionAuth": []}]
        return
    operation["security"] = [
        {"BearerAuth": []},
        {"CookieSessionAuth": [], "CsrfHeader": []},
    ]


def _customize_openapi(app: FastAPI) -> dict[str, Any]:
    schema = get_openapi(
        title="QMTool Backend API",
        version="1.0.0",
        description=(
            "Clientneutraler HTTP-Vertrag fuer QMTool J04-M0. "
            "Fachliche Mutationen verwenden bestaetigte Sessions und optimistische "
            "ETag-Sperren."
        ),
        routes=app.routes,
        tags=[
            {"name": "auth", "description": "Login, Session und Passwortwechsel."},
            {"name": "users", "description": "Directory- und administrative Benutzervertraege."},
            {"name": "documents", "description": "Dokumentenpool, Artefakte und Workflow."},
            {"name": "signature", "description": "Signatur- und Signaturvorlagenvertrag."},
            {"name": "health", "description": "Betriebsbereitschaft."},
        ],
    )
    schema["info"]["x-qmtool-work-package"] = "J04-M0"
    schema["components"].setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "opaque session token",
        "description": "Opaque Bearer-Session aus POST /api/v1/auth/token; nicht persistieren.",
    }
    schema["components"]["securitySchemes"]["CookieSessionAuth"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": "qmtool_session",
        "description": "HttpOnly session cookie fuer Browser-Clients (Same-Origin).",
    }
    schema["components"]["securitySchemes"]["CsrfHeader"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-CSRF-Token",
        "description": "CSRF double-submit header; muss qmtool_csrf Cookie entsprechen.",
    }
    schema["components"].setdefault("schemas", {})["ErrorDetail"] = {
        "type": "object",
        "required": ["error", "message"],
        "properties": {
            "error": {"type": "string", "example": "document_conflict"},
            "message": {"type": "string", "example": "document state is newer"},
            "current_etag": {"type": "string", "nullable": True, "example": "evt-42"},
            "current_state": {"type": "object", "nullable": True, "additionalProperties": True},
        },
    }
    # Ensure public conflict field name is current_state only.
    error_detail = schema["components"]["schemas"]["ErrorDetail"]
    properties = error_detail.get("properties", {})
    properties.pop("state", None)
    schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "required": ["detail"],
        "properties": {
            "detail": {
                "oneOf": [
                    {"$ref": "#/components/schemas/ErrorDetail"},
                    {"type": "array", "items": {"type": "object"}},
                ]
            }
        },
        "examples": [
            {"detail": {"error": "unauthorized", "message": "missing bearer token"}},
            {
                "detail": {
                    "error": "document_conflict",
                    "message": "document state is newer",
                    "current_etag": "evt-42",
                    "current_state": {"document_id": "DOC-1", "version": 1},
                }
            },
        ],
    }

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            operation.setdefault("operationId", f"{method}_{re.sub(r'[^A-Za-z0-9]+', '_', path).strip('_').lower()}")
            operation.setdefault("summary", operation["operationId"].replace("_", " ").capitalize())
            operation.setdefault("description", "QMTool J04-M0 HTTP operation.")
            _apply_operation_security(path, method, operation)
            for status_code in _ERROR_STATUS_CODES:
                operation.setdefault("responses", {}).setdefault(
                    str(status_code),
                    {
                        "description": "Structured QMTool error response.",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                )
            _add_header_parameter(
                operation,
                "X-Request-ID",
                "Optional correlation identifier echoed by the backend.",
                required=False,
            )
            _apply_if_match_contract(path, method, operation)
            if path.endswith("/content"):
                response_200 = operation.setdefault("responses", {}).setdefault("200", {"description": "Binary artifact."})
                response_200["content"] = {
                    media_type: {"schema": {"type": "string", "format": "binary"}}
                    for media_type in (
                        "application/pdf",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "image/png",
                        "image/gif",
                        "application/octet-stream",
                    )
                }
            if any(marker in path for marker in ("/import-pdf", "/import-docx", "/create-from-template", "/assets/import")):
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        media_type: {"schema": {"type": "string", "format": "binary"}}
                        for media_type in (
                            "application/pdf",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
                            "image/png",
                            "application/octet-stream",
                        )
                    },
                }
    _require_available_actions_on_state_responses(schema)
    return schema


def create_app(container=None) -> FastAPI:
    """Create the backend app and its complete client-neutral contract.

    Routers are always registered so a container-free app can export the complete
    OpenAPI document. Fachliche calls fail closed with HTTP 503 until wired.
    """
    production = os.environ.get("QMTOOL_RUNTIME_PROFILE", "").strip().lower() in _PRODUCTION_PROFILES
    app = FastAPI(
        title="QMTool Backend API",
        version="1.0.0",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        generate_unique_id_function=_stable_operation_id,
    )
    app.state.container = container

    @app.middleware("http")
    async def cookie_csrf_guard(request: Request, call_next: Callable) -> Response:
        return await enforce_cookie_csrf(request, call_next)

    @app.middleware("http")
    async def maintenance_gate(request: Request, call_next: Callable) -> Response:
        if (
            is_maintenance_active()
            and request.method.upper() not in SAFE_METHODS
            and request.url.path != "/health"
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": {
                        "error": "maintenance_mode",
                        "message": "installation is in maintenance mode; state-changing requests are unavailable",
                    }
                },
            )
        return await call_next(request)

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

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def _health() -> HealthResponse:
        return HealthResponse(status="ok", service="qmtool-backend")

    app.include_router(auth_router, prefix=_API_V1)
    app.include_router(user_admin_router, prefix=_API_V1)
    app.include_router(documents_router, prefix=_API_V1)
    app.include_router(signature_router, prefix=_API_V1)

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = _customize_openapi(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]

    webclient_dist = resolve_webclient_dist_dir()
    if webclient_dist is not None:
        app.mount(
            "/",
            StaticFiles(directory=str(webclient_dist), html=True),
            name="webclient-static",
        )

    return app
