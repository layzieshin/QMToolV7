from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from src.backend.container_demo import build_demo_app


def blueprint_payload():
    return {
        "key": "runtime-test",
        "name": "Prüfmanagement",
        "description": "Laufzeitprojektion für den Thin Client",
        "root_template_key": "inspection",
        "templates": [
            {
                "key": "inspection",
                "kind": "OBJECT",
                "name": "Prüfung",
                "create_roles": ["ADMIN"],
                "initial_state": "DRAFT",
                "fields": [
                    {"key": "title", "field_type": "string", "required": True, "searchable": True},
                    {"key": "internal", "field_type": "string", "visible": False},
                ],
                "lifecycle_states": [
                    {"code": "DRAFT", "initial": True},
                    {"code": "APPROVED"},
                ],
                "lifecycle_transitions": [
                    {
                        "from_state": "DRAFT",
                        "to_state": "APPROVED",
                        "allowed_roles": ["QMB"],
                        "signature_required": True,
                    }
                ],
            },
            {
                "key": "evidence",
                "kind": "ARTIFACT",
                "name": "Nachweis",
                "create_roles": ["ADMIN"],
                "fields": [{"key": "title", "field_type": "string", "required": True}],
            },
        ],
    }


def test_runtime_http_projection_and_owned_artifacts(tmp_path: Path):
    demo_app = build_demo_app(tmp_path / "demo")
    client = TestClient(demo_app)
    published = client.post("/container/blueprints/publish", json=blueprint_payload()).json()

    runtime = client.get("/container/runtime-modules")
    assert runtime.status_code == 200
    module = runtime.json()[0]
    root_template = next(template for template in module["templates"] if template["is_root"])
    assert [field["key"] for field in root_template["fields"]] == ["title"]
    assert "allowed_roles" not in root_template["lifecycle_transitions"][0]

    workspace_uid = client.get("/container/workspace-root").json()["uid"]
    created = client.post(
        "/container/objects",
        json={
            "template_version_uid": published["root_template_version_uid"],
            "parent_kind": "WORKSPACE_ROOT",
            "parent_uid": workspace_uid,
            "values": {"title": "Lieferantenprüfung"},
        },
    ).json()
    artifact_template = next(item for item in published["templates"] if item["template_key"] == "evidence")
    artifact = client.post(
        "/container/artifacts",
        json={
            "template_version_uid": artifact_template["template_version_uid"],
            "owner_object_uid": created["uid"],
            "values": {"title": "Ergebnis"},
        },
    ).json()

    detail = client.get(f"/container/objects/{created['uid']}")
    assert detail.status_code == 200
    assert [item["uid"] for item in detail.json()["artifacts"]] == [artifact["uid"]]
    assert [item["uid"] for item in client.get("/container/runtime-modules").json()[0]["root_objects"]] == [
        created["uid"]
    ]

    production_shape = TestClient(create_app(demo_app.state.container))
    assert production_shape.get("/container/runtime-modules").status_code == 401
