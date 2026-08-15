import base64
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from src.backend.container_demo import build_demo_app
from src.backend import container_routes


def _draft(client, kind, name):
    response = client.post("/container/templates/drafts", json={"kind": kind, "name": name, "version_number": 1, "create_roles": ["ADMIN"], "fields": [{"key": "title", "field_type": "string", "required": True, "searchable": True}]})
    assert response.status_code == 200
    uid = response.json()["uid"]
    assert client.post(f"/container/templates/{uid}/publish").status_code == 200
    return uid


def test_routes_auth_strict_and_full_happy_path(tmp_path: Path, monkeypatch):
    normal = TestClient(create_app(build_demo_app(tmp_path).state.container))
    assert normal.get("/container/status").status_code == 401
    client = TestClient(build_demo_app(tmp_path / "demo"))
    assert client.post("/container/templates/drafts", json={"kind": "OBJECT", "name": "x", "version_number": 1, "create_roles": ["ADMIN"], "global_roles": ["ADMIN"]}).status_code == 422
    assert client.post("/container/templates/drafts", json={"kind": "OBJECT", "name": "x", "version_number": 1, "create_roles": ["ADMIN"], "fields": [{"key": "bad", "field_type": "wat"}]}).status_code == 422
    missing_child = client.post("/container/templates/drafts", json={"kind": "OBJECT", "name": "x", "version_number": 1, "create_roles": ["ADMIN"], "children": [{"key": "missing", "template_version_uid": "missing"}]})
    assert missing_child.status_code == 404
    assert missing_child.json()["detail"]["code"] == "container.template.child_template_not_found"
    root = client.get("/container/workspace-root").json()["uid"]
    object_template = _draft(client, "OBJECT", "Object")
    obj = client.post("/container/objects", json={"template_version_uid": object_template, "parent_kind": "WORKSPACE_ROOT", "parent_uid": root, "values": {"title": "hello"}}).json()
    search = client.get("/container/objects/search", params={"query": "hello", "field_keys": "title"})
    assert search.status_code == 200 and [item["uid"] for item in search.json()] == [obj["uid"]]
    artifact_template = _draft(client, "ARTIFACT", "Artifact")
    artifact = client.post("/container/artifacts", json={"template_version_uid": artifact_template, "owner_object_uid": obj["uid"], "values": {"title": "file"}}).json()
    assert "allowed_actions" in client.get(f'/container/objects/{obj["uid"]}').json()
    bad = client.post(f'/container/artifacts/{artifact["uid"]}/files', json={"original_name": "x", "media_type": "text/plain", "content_base64": "!", "expected_revision": 1})
    assert bad.status_code == 422
    bad_name = client.post(f'/container/artifacts/{artifact["uid"]}/files', json={"original_name": "../x", "media_type": "text/plain", "content_base64": "aGk=", "expected_revision": 1})
    assert bad_name.status_code == 422
    header_name = client.post(f'/container/artifacts/{artifact["uid"]}/files', json={"original_name": "x\r\ny.txt", "media_type": "text/plain", "content_base64": "aGk=", "expected_revision": 1})
    assert header_name.status_code == 422
    uploaded = client.post(f'/container/artifacts/{artifact["uid"]}/files', json={"original_name": "prüf.txt", "media_type": "text/plain", "content_base64": base64.b64encode(b"hello").decode(), "expected_revision": 1})
    assert uploaded.status_code == 200
    file_uid = uploaded.json()["uid"]
    download = client.get(f'/container/artifacts/{artifact["uid"]}/files/{file_uid}/download')
    assert download.content == b"hello" and "attachment" in download.headers["content-disposition"]
    assert "%C3%BC" in download.headers["content-disposition"] and "\r" not in download.headers["content-disposition"]
    monkeypatch.setattr(container_routes, "MAX_UPLOAD_BYTES", 2)
    too_large = client.post(f'/container/artifacts/{artifact["uid"]}/files', json={"original_name": "large.bin", "media_type": "application/octet-stream", "content_base64": base64.b64encode(b"123").decode(), "expected_revision": 2})
    assert too_large.status_code == 422 and too_large.json()["detail"]["code"] == "container.storage.file_too_large"
    assert client.post(f'/container/artifacts/{artifact["uid"]}/finalize', json={"expected_revision": 2}).status_code == 200
    assert client.put(f'/container/artifacts/{artifact["uid"]}/fields', json={"values": {"title": "no"}, "expected_revision": 2}).status_code == 409
