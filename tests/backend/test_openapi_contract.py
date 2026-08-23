from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import (
    _DOCUMENTS_CREATE_FROM_TEMPLATE,
    _DOCUMENTS_IF_MATCH_REQUIRED,
    _DOCUMENTS_STATE_RESPONSE_SCHEMAS,
    create_app,
)


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "docs" / "contracts" / "j04-m0-openapi.json"


def _operations(document: dict[str, object]):
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                yield path, method, operation


def _if_match_parameter(operation: dict[str, object]) -> dict[str, object] | None:
    for parameter in operation.get("parameters") or []:
        if parameter.get("name") == "If-Match" and parameter.get("in") == "header":
            return parameter
    return None


def test_dev_exposes_swagger_redoc_and_openapi(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["x-qmtool-work-package"] == "J04-M0"


def test_production_hides_dynamic_openapi_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("QMTOOL_RUNTIME_PROFILE", "production")
    app = create_app()
    client = TestClient(app)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    # The in-process export remains available to the build/export step.
    assert "/api/v1/documents/pool/by-status/{status}" in app.openapi()["paths"]


def test_openapi_has_complete_j04_routes_and_unique_operation_ids(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    document = create_app().openapi()
    operations = list(_operations(document))
    ids = [str(operation["operationId"]) for _path, _method, operation in operations]
    assert len(ids) == len(set(ids))
    assert {"auth", "users", "documents", "signature"}.issubset(
        {tag for _path, _method, operation in operations for tag in operation.get("tags", [])}
    )
    assert "/api/v1/auth/csrf" in document["paths"]
    assert "/api/v1/auth/token" in document["paths"]
    assert "/api/v1/auth/login" in document["paths"]
    assert "/api/v1/auth/me" in document["paths"]
    assert "/api/v1/documents/pool/by-status/{status}" in document["paths"]
    assert "/api/v1/documents/versions/{document_id}/{version}" in document["paths"]
    assert "/api/v1/signature/templates/user" in document["paths"]


def test_openapi_security_headers_and_binary_contract(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    document = create_app().openapi()
    assert "BearerAuth" in document["components"]["securitySchemes"]
    assert "CookieSessionAuth" in document["components"]["securitySchemes"]
    assert "CsrfHeader" in document["components"]["securitySchemes"]
    assert "security" not in document["paths"]["/health"]["get"]
    assert "security" not in document["paths"]["/api/v1/auth/login"]["post"]
    assert "security" not in document["paths"]["/api/v1/auth/token"]["post"]
    assert "security" not in document["paths"]["/api/v1/auth/csrf"]["get"]
    me_security = document["paths"]["/api/v1/auth/me"]["get"]["security"]
    assert {"BearerAuth": []} in me_security
    assert {"CookieSessionAuth": []} in me_security

    mutation = document["paths"]["/api/v1/documents/versions/{document_id}/{version}/workflow/start"]["post"]
    if_match = _if_match_parameter(mutation)
    assert if_match is not None
    assert if_match["required"] is True
    assert "409" in mutation["responses"]
    assert "428" in mutation["responses"]
    assert "ETag" in mutation["responses"]["200"]["headers"]

    binary = document["paths"]["/api/v1/documents/artifacts/{artifact_id}/content"]["get"]["responses"]["200"]
    assert {"application/pdf", "image/png", "application/octet-stream"}.issubset(binary["content"])
    assert "ErrorDetail" in document["components"]["schemas"]
    raw = json.dumps(document, ensure_ascii=True)
    for forbidden in ("QMTOOL_PG_PASSWORD=", "documents.db", "storage_key", "I:/Projekte/"):
        assert forbidden not in raw


def test_openapi_if_match_required_set_and_428_coverage(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    document = create_app().openapi()
    required = {
        (method, path)
        for path, method, operation in _operations(document)
        if (param := _if_match_parameter(operation)) is not None and param.get("required") is True
    }
    assert required == _DOCUMENTS_IF_MATCH_REQUIRED
    for method, path in _DOCUMENTS_IF_MATCH_REQUIRED:
        operation = document["paths"][path][method]
        assert "428" in operation["responses"]
        assert "409" in operation["responses"]
        assert _if_match_parameter(operation)["required"] is True


def test_openapi_create_from_template_if_match_is_conditional(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    document = create_app().openapi()
    method, path = _DOCUMENTS_CREATE_FROM_TEMPLATE
    operation = document["paths"][path][method]
    if_match = _if_match_parameter(operation)
    assert if_match is not None
    assert if_match["required"] is False
    assert "already exists" in if_match["description"]
    assert "428" in operation["responses"]
    assert "409" in operation["responses"]
    assert "already exists" in operation["description"]


def test_openapi_non_documents_mutations_have_no_if_match(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    document = create_app().openapi()
    for path, method, operation in _operations(document):
        key = (method, path)
        if key in _DOCUMENTS_IF_MATCH_REQUIRED or key == _DOCUMENTS_CREATE_FROM_TEMPLATE:
            continue
        assert _if_match_parameter(operation) is None, f"unexpected If-Match on {method.upper()} {path}"


def test_openapi_error_detail_and_available_actions_contract(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    document = create_app().openapi()
    detail = document["components"]["schemas"]["ErrorDetail"]
    assert "current_state" in detail["properties"]
    assert "state" not in detail["properties"]
    schemas = document["components"]["schemas"]
    for name in _DOCUMENTS_STATE_RESPONSE_SCHEMAS:
        model = schemas[name]
        assert "available_actions" in model["required"]
        assert model["properties"]["available_actions"]["type"] == "array"


def test_openapi_snapshot_is_reproducible(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_RUNTIME_PROFILE", raising=False)
    assert SNAPSHOT.is_file()
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    actual = create_app().openapi()
    assert expected == actual
