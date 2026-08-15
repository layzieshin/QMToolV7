from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from src.backend.container_demo import build_demo_app


def test_admin_builder_is_complete_and_demo_only(tmp_path: Path):
    demo_app = build_demo_app(tmp_path / "demo")
    client = TestClient(demo_app)

    page = client.get("/container/admin")
    assert page.status_code == 200
    assert "QMTool Modulwerkstatt" in page.text
    assert "Lokale Testoberfläche" in page.text
    assert 'id="template-tree"' in page.text
    assert 'data-action="publish"' in page.text
    assert 'data-view="preview"' in page.text

    styles = client.get("/container/admin/app.css")
    script = client.get("/container/admin/app.js")
    assert styles.status_code == 200 and "--accent" in styles.text
    assert script.status_code == 200
    for endpoint in (
        "/container/blueprints/validate",
        "/container/blueprints/publish",
        "/container/blueprints",
        "/container/workspace-root",
        "/container/objects",
    ):
        assert endpoint in script.text

    landing = client.get("/container/demo").json()
    assert landing["admin"] == "/container/admin"

    build_script = Path("packaging/build_onedir.py").read_text(encoding="utf-8")
    assert '("src/backend/static/container_admin", "src/backend/static/container_admin")' in build_script

    production_shape = TestClient(create_app(demo_app.state.container))
    assert production_shape.get("/container/admin").status_code == 404


def test_admin_builder_survives_demo_restart(tmp_path: Path):
    first = TestClient(build_demo_app(tmp_path))
    assert first.get("/container/admin").status_code == 200
    second = TestClient(build_demo_app(tmp_path))
    assert second.get("/container/admin/app.js").status_code == 200


def test_builder_guide_uses_the_live_labels_and_route(tmp_path: Path):
    guide = Path("docs/container-module/MODULE_BUILDER_GUIDE.md").read_text(encoding="utf-8")
    page = TestClient(build_demo_app(tmp_path)).get("/container/admin").text
    assert "http://127.0.0.1:8765/container/admin" in guide
    for label in ("Struktur", "Testlauf", "Import", "Export", "Prüfen", "Veröffentlichen"):
        assert label in guide and label in page
    assert "tests/backend/test_container_blueprint_routes.py" in guide
