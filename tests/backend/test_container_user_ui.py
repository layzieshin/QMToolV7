from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from src.backend.container_demo import build_demo_app


def test_end_user_workspace_is_complete_and_demo_only(tmp_path: Path):
    demo_app = build_demo_app(tmp_path / "demo")
    client = TestClient(demo_app)

    page = client.get("/container/app")
    assert page.status_code == 200
    assert "QMTool Arbeitsbereich" in page.text
    assert "Veröffentlichte Module" in page.text
    assert "Single-Unit-Testbetrieb" in page.text
    assert 'id="module-list"' in page.text
    assert 'id="object-tree"' in page.text
    assert 'id="search-form"' in page.text
    assert 'href="/container/admin"' in page.text

    styles = client.get("/container/app/app.css")
    script = client.get("/container/app/app.js")
    assert styles.status_code == 200 and "--accent" in styles.text
    assert script.status_code == 200
    for endpoint in (
        "/container/runtime-modules",
        "/container/workspace-root",
        "/container/objects/search",
        "/container/objects",
        "/container/artifacts",
    ):
        assert endpoint in script.text
    for capability in (
        'isAllowed(detail, "UPDATE")',
        'isAllowed(detail, "CREATE_CHILD")',
        'isAllowed(detail, "CREATE_ARTIFACT")',
        'isAllowed(detail, "TRANSITION")',
    ):
        assert capability in script.text

    production_shape = TestClient(create_app(demo_app.state.container))
    assert production_shape.get("/container/app").status_code == 404
    assert production_shape.get("/container/app/app.js").status_code == 404


def test_end_user_client_does_not_claim_identity_or_roles(tmp_path: Path):
    script = TestClient(build_demo_app(tmp_path)).get("/container/app/app.js").text
    forbidden_claims = (
        "global_roles",
        "is_qmb",
        "X-Actor",
        "X-Role",
        '"ADMIN"',
        '"QMB"',
        "localStorage",
        "sessionStorage",
    )
    assert all(claim not in script for claim in forbidden_claims)
    assert "allowed_actions" in script


def test_end_user_workspace_survives_demo_restart(tmp_path: Path):
    first = TestClient(build_demo_app(tmp_path))
    assert first.get("/container/app").status_code == 200
    second = TestClient(build_demo_app(tmp_path))
    assert second.get("/container/app/app.js").status_code == 200


def test_end_user_guide_matches_live_ui_and_start_path(tmp_path: Path):
    guide = Path("docs/container-module/END_USER_DEMO_GUIDE.md").read_text(encoding="utf-8")
    client = TestClient(build_demo_app(tmp_path))
    surface = client.get("/container/app").text + client.get("/container/app/app.js").text

    assert "python -m src.backend.container_demo --app-home build/container-demo --port 8765" in guide
    assert "http://127.0.0.1:8765/container/demo" in guide
    assert "/container/admin" in guide and "/container/admin" in surface
    for label in (
        "Modulwerkstatt",
        "Aktualisieren",
        "Neuer Haupteintrag",
        "Bearbeiten",
        "Untereintrag",
        "Nachweis",
        "Finalisieren",
        "Verlauf laden",
    ):
        assert label in guide and label in surface
    for test_path in (
        "tests/backend/test_container_user_ui.py",
        "tests/backend/test_container_runtime_routes.py",
        "tests/modules/container/test_container_m6_runtime_projection.py",
    ):
        assert test_path in guide

    build_script = Path("packaging/build_onedir.py").read_text(encoding="utf-8")
    assert '("src/backend/static/container_user", "src/backend/static/container_user")' in build_script
