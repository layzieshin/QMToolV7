from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from tests.backend.test_documents_http_api import _auth, _login
from tests.backend.test_signature_http_api import _build_signature_backend, _create_signature_png


_TEMPLATE = {
    "name": "global-template",
    "placement": {"page_index": 0, "x": 72.0, "y": 72.0, "target_width": 120.0},
    "layout": {"show_signature": False, "show_name": True, "show_date": True},
}


def test_global_template_crud_is_technical_admin_only(tmp_path: Path) -> None:
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    observer = _login(client, "observer", "observerpass01")
    admin = _login(client, "admin", "adminpass01")

    denied = client.post(
        "/signature/templates/user",
        headers=_auth(observer),
        json={**_TEMPLATE, "scope": "global"},
    )
    assert denied.status_code == 403, denied.text

    created = client.post(
        "/signature/templates/user",
        headers=_auth(admin),
        json={**_TEMPLATE, "scope": "global"},
    )
    assert created.status_code == 200, created.text
    template_id = created.json()["template_id"]
    observer_delete = client.delete(
        f"/signature/templates/{template_id}", headers=_auth(observer)
    )
    assert observer_delete.status_code == 403, observer_delete.text


def test_global_template_can_be_copied_to_personal_scope(tmp_path: Path) -> None:
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    observer = _login(client, "observer", "observerpass01")
    created = client.post(
        "/signature/templates/user",
        headers=_auth(admin),
        json={**_TEMPLATE, "scope": "global"},
    )
    template_id = created.json()["template_id"]
    copied = client.post(
        f"/signature/templates/global/{template_id}/copy",
        headers=_auth(observer),
        json={"name": "observer-copy"},
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["scope"] == "user"
    assert copied.json()["owner_user_id"] == "observer"


def test_global_template_copy_clones_foreign_signature_asset(tmp_path: Path) -> None:
    container, _users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    observer = _login(client, "observer", "observerpass01")
    png = tmp_path / "global-signature.png"
    _create_signature_png(png)
    imported = client.post(
        "/signature/assets/import-and-activate",
        headers={**_auth(admin), "Content-Type": "image/png", "X-Filename-Hint": png.name},
        content=png.read_bytes(),
    )
    assert imported.status_code == 200, imported.text
    asset_id = imported.json()["asset_id"]
    created = client.post(
        "/signature/templates/user",
        headers=_auth(admin),
        json={
            **_TEMPLATE,
            "scope": "global",
            "signature_asset_id": asset_id,
            "layout": {"show_signature": True, "show_name": True, "show_date": True},
        },
    )
    assert created.status_code == 200, created.text
    copied = client.post(
        f"/signature/templates/global/{created.json()['template_id']}/copy",
        headers=_auth(observer),
        json={"name": "observer-copy-with-asset"},
    )
    assert copied.status_code == 200, copied.text
    copied_asset_id = copied.json()["signature_asset_id"]
    assert copied_asset_id != asset_id
    copied_asset = container.get_port("signature_service").repository.get_asset(copied_asset_id)
    assert copied_asset is not None
    assert copied_asset.owner_user_id == "observer"
