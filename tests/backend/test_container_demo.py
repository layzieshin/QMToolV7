from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.container_demo import build_demo_app


def test_demo_is_explicit_isolated_and_idempotent(tmp_path: Path, monkeypatch):
    outside_db = tmp_path.parent / "poison-container.db"
    outside_files = tmp_path.parent / "poison-artifacts"
    monkeypatch.setenv("QMTOOL_DB_CONTAINER_PATH", str(outside_db))
    monkeypatch.setenv("QMTOOL_PATH_CONTAINER_ARTIFACT_FILES_ROOT", str(outside_files))
    first = TestClient(build_demo_app(tmp_path))
    assert first.get("/docs").status_code == 200
    assert "LOCAL DEMO" in first.get("/openapi.json").json()["info"]["title"]
    assert first.get("/auth/me").status_code == 404
    assert first.get("/container/status").status_code == 200
    assert (tmp_path / "storage/container/container.db").is_file()
    assert not outside_db.exists() and not outside_files.exists()
    second = TestClient(build_demo_app(tmp_path))
    assert second.get("/container/status").status_code == 200
