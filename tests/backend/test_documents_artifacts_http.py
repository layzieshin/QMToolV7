"""J04-M0-P3A: documents artifact HTTP transport."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _create_assign_start,
    _login,
    _mutation_headers,
)


def test_artifact_list_metadata_and_download_omit_storage_key(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-ART-1")
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 artifact-transport-test\n%%EOF\n")

    detail = client.get("/api/v1/documents/versions/DOC-ART-1/1", headers=_auth(tokens["editor"]))
    assert detail.status_code == 200, detail.text
    etag = detail.json()["etag"]

    uploaded = client.post(
        "/api/v1/documents/versions/DOC-ART-1/1/import-pdf",
        headers=_mutation_headers(tokens["admin"], etag, extra={"Content-Type": "application/pdf"}),
        content=pdf.read_bytes(),
    )
    assert uploaded.status_code == 200, uploaded.text

    listed = client.get("/api/v1/documents/versions/DOC-ART-1/1/artifacts", headers=_auth(tokens["editor"]))
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert rows
    row = rows[0]
    assert "storage_key" not in row
    assert "path" not in row
    assert row["artifact_id"]
    assert row["sha256"]
    assert "storage_key" not in str(row.get("metadata", {})).lower()

    meta = client.get(f"/api/v1/documents/artifacts/{row['artifact_id']}", headers=_auth(tokens["editor"]))
    assert meta.status_code == 200
    assert "storage_key" not in meta.json()

    content = client.get(
        f"/api/v1/documents/artifacts/{row['artifact_id']}/content",
        headers=_auth(tokens["editor"]),
    )
    assert content.status_code == 200
    assert content.content.startswith(b"%PDF")
    assert content.headers.get("X-Content-SHA256") == row["sha256"]
    assert content.headers.get("ETag") == row["sha256"]
    assert int(content.headers.get("Content-Length", "0")) == len(content.content)


def test_ensure_source_pdf_after_import_returns_downloadable_artifact(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-ENSURE-PDF")
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 ensure-source-pdf\n%%EOF\n")

    detail = client.get("/api/v1/documents/versions/DOC-ENSURE-PDF/1", headers=_auth(tokens["editor"]))
    assert detail.status_code == 200, detail.text

    uploaded = client.post(
        "/api/v1/documents/versions/DOC-ENSURE-PDF/1/import-pdf",
        headers=_mutation_headers(tokens["admin"], detail, extra={"Content-Type": "application/pdf"}),
        content=pdf.read_bytes(),
    )
    assert uploaded.status_code == 200, uploaded.text

    ensured = client.post(
        "/api/v1/documents/versions/DOC-ENSURE-PDF/1/workflow/ensure-source-pdf",
        headers=_mutation_headers(tokens["editor"], uploaded),
        json={},
    )
    assert ensured.status_code == 200, ensured.text
    body = ensured.json()
    assert body.get("artifact_id")
    download = client.get(
        f"/api/v1/documents/artifacts/{body['artifact_id']}/content",
        headers=_auth(tokens["editor"]),
    )
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")


def test_oversized_pdf_upload_rejected(tmp_path: Path, monkeypatch) -> None:
    from src.backend import documents_routes as routes

    monkeypatch.setattr(routes, "MAX_UPLOAD_BYTES", 64)
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/api/v1/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-ART-BIG", "version": 1},
    )
    assert created.status_code == 200, created.text
    etag = created.json()["etag"]
    body = b"%PDF-1.4 " + (b"x" * 128)
    response = client.post(
        "/api/v1/documents/versions/DOC-ART-BIG/1/import-pdf",
        headers=_mutation_headers(admin, etag, extra={"Content-Type": "application/pdf"}),
        content=body,
    )
    assert response.status_code in {400, 413}


def test_import_scratch_target_stays_in_scratch_root(tmp_path: Path) -> None:
    from src.backend.documents_routes import _import_scratch_target

    root = tmp_path / "scratch" / "imports"
    target = _import_scratch_target(root, ".pdf")
    assert target.is_relative_to(root.resolve())
    assert target.parent == root.resolve()
    assert target.suffix == ".pdf"
    assert target.stem.isalnum()
    assert len(target.stem) == 32
