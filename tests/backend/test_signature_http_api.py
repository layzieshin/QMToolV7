"""J04-M0-P3B: signature HTTP API tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.signature.wiring import register_signature_ports
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _login,
    _minimal_pdf_bytes,
)
from tests.database_helpers import prepare_test_database


def _create_signature_png(path: Path) -> None:
    if importlib.util.find_spec("PIL") is None:
        pytest.skip("PIL not installed")
    from PIL import Image

    img = Image.new("RGBA", (120, 40), (255, 255, 255, 0))
    for x in range(10, 110):
        img.putpixel((x, 20 + (x % 5)), (0, 0, 0, 255))
    img.save(path, format="PNG")


def _wire_signature_module(container, root: Path) -> None:
    settings = container.get_port("settings_service")
    settings.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    settings.set_module_settings(
        "signature",
        {"require_password": False, "default_mode": "visual"},
        acknowledge_governance_change=True,
        actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
    )
    sig_db = root / "storage" / "signature" / "templates.db"
    sig_db.parent.mkdir(parents=True, exist_ok=True)
    prepare_test_database("signature", sig_db)
    (root / "storage" / "signature" / "assets").mkdir(parents=True, exist_ok=True)
    (root / "storage" / "platform").mkdir(parents=True, exist_ok=True)
    container.register_port("signature_runtime_owner", "backend")
    register_signature_ports(container)
    if container.has_port("documents_service"):
        container.get_port("documents_service")._signature_api = container.get_port("signature_api")


def _build_signature_backend(tmp_path: Path):
    container, users = _build_documents_backend_container(tmp_path)
    _wire_signature_module(container, tmp_path)
    return container, users


def test_verify_password_and_asset_roundtrip(tmp_path: Path) -> None:
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    editor = _login(client, "editor", "editorpass01")

    png = tmp_path / "sig.png"
    _create_signature_png(png)
    imported = client.post(
        "/signature/assets/import-and-activate",
        headers={**_auth(editor), "Content-Type": "image/png", "X-Filename-Hint": "sig.png"},
        content=png.read_bytes(),
    )
    assert imported.status_code == 200, imported.text
    asset_id = imported.json()["asset_id"]

    active = client.get("/signature/assets/active/id", headers=_auth(editor))
    assert active.status_code == 200
    assert active.json()["asset_id"] == asset_id

    exported = client.get("/signature/assets/active/content", headers=_auth(editor))
    assert exported.status_code == 200
    assert exported.content.startswith(b"\x89PNG")

    verify = client.post("/signature/verify-password", headers=_auth(editor), json={"password": "editorpass01"})
    assert verify.status_code == 200
    assert verify.json()["ok"] is True


def test_standalone_sign_upload_handle(tmp_path: Path) -> None:
    if importlib.util.find_spec("pypdf") is None or importlib.util.find_spec("reportlab") is None:
        pytest.skip("visual signing dependencies missing")
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    editor = _login(client, "editor", "editorpass01")

    png = tmp_path / "sig.png"
    _create_signature_png(png)
    assert client.post(
        "/signature/assets/import-and-activate",
        headers={**_auth(editor), "Content-Type": "image/png"},
        content=png.read_bytes(),
    ).status_code == 200

    upload = client.post(
        "/signature/standalone/upload",
        headers={**_auth(editor), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert upload.status_code == 200, upload.text
    handle = upload.json()["upload_handle"]

    signed = client.post(
        "/signature/standalone/sign",
        headers=_auth(editor),
        json={
            "upload_handle": handle,
            "placement": {"page_index": 0, "x": 72.0, "y": 72.0, "target_width": 120.0},
            "layout": {
                "show_signature": True,
                "show_name": True,
                "show_date": True,
                "name_position": "above",
                "date_position": "below",
            },
            "reason": "standalone_test",
        },
    )
    assert signed.status_code == 200, signed.text
    assert signed.content.startswith(b"%PDF")
    leftover = [
        path
        for path in tmp_path.joinpath("scratch").rglob("*")
        if path.is_file() and path.suffix.lower() in {".pdf", ".png"}
    ]
    assert leftover == []


def test_export_active_content_leaves_no_export_file(tmp_path: Path) -> None:
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    editor = _login(client, "editor", "editorpass01")
    png = tmp_path / "sig.png"
    _create_signature_png(png)
    assert client.post(
        "/signature/assets/import-and-activate",
        headers={**_auth(editor), "Content-Type": "image/png"},
        content=png.read_bytes(),
    ).status_code == 200
    exported = client.get("/signature/assets/active/content", headers=_auth(editor))
    assert exported.status_code == 200, exported.text
    assert exported.content.startswith(b"\x89PNG")
    export_dir = tmp_path / "scratch" / "signature-export"
    leftover = [path for path in export_dir.rglob("*") if path.is_file()] if export_dir.exists() else []
    assert leftover == []


def test_standalone_sign_error_cleans_scratch(tmp_path: Path) -> None:
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    editor = _login(client, "editor", "editorpass01")
    upload = client.post(
        "/signature/standalone/upload",
        headers={**_auth(editor), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert upload.status_code == 200, upload.text
    failed = client.post(
        "/signature/standalone/sign",
        headers=_auth(editor),
        json={
            "upload_handle": upload.json()["upload_handle"],
            "placement": {"page_index": 0, "x": 72.0, "y": 72.0, "target_width": 120.0},
            "layout": {"show_signature": True},
            "reason": "missing-active",
        },
    )
    assert failed.status_code != 200, failed.text
    leftover = [
        path
        for path in tmp_path.joinpath("scratch").rglob("*")
        if path.is_file() and path.suffix.lower() in {".pdf", ".png"}
    ]
    assert leftover == []


def test_upload_store_purges_only_own_root(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    container, _users = _build_signature_backend(tmp_path)
    app = create_app(container)
    client = TestClient(app)
    editor = _login(client, "editor", "editorpass01")
    first = client.post(
        "/signature/standalone/upload",
        headers={**_auth(editor), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert first.status_code == 200, first.text
    uploads = tmp_path / "scratch" / "signature-uploads"
    orphan = uploads / "orphan.pdf"
    orphan.write_bytes(b"%PDF-orphan")
    foreign = tmp_path / "foreign.pdf"
    foreign.write_bytes(b"%PDF-foreign")
    handle = first.json()["upload_handle"]
    path, owner, _expires = app.state.signature_upload_handles[handle]
    app.state.signature_upload_handles[handle] = (
        path,
        owner,
        datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    second = client.post(
        "/signature/standalone/upload",
        headers={**_auth(editor), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert second.status_code == 200, second.text
    assert not orphan.exists()
    assert not path.exists()
    assert foreign.exists()
    assert handle not in app.state.signature_upload_handles
