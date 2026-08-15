from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.container_demo import build_demo_app


def blueprint_payload():
    return {
        "key": "device-management",
        "name": "Gerätemanagement",
        "description": "Geräte und Wartungen",
        "root_template_key": "device",
        "templates": [
            {
                "key": "device",
                "kind": "OBJECT",
                "name": "Gerät",
                "create_roles": ["ADMIN", "QMB"],
                "fields": [
                    {
                        "key": "serial_number",
                        "field_type": "string",
                        "required": True,
                        "searchable": True,
                    }
                ],
                "children": [
                    {
                        "key": "maintenance",
                        "template_key": "maintenance",
                        "min_count": 1,
                        "max_count": 1,
                        "auto_create": True,
                        "mode": "FIXED",
                    }
                ],
                "lifecycle_states": [
                    {"code": "ACTIVE", "initial": True},
                    {"code": "OUT_OF_SERVICE", "initial": False},
                ],
                "lifecycle_transitions": [
                    {
                        "from_state": "ACTIVE",
                        "to_state": "OUT_OF_SERVICE",
                        "allowed_roles": ["QMB"],
                        "reason_required": True,
                    }
                ],
            },
            {
                "key": "maintenance",
                "kind": "OBJECT",
                "name": "Wartung",
                "create_roles": ["ADMIN", "QMB"],
                "fields": [{"key": "note", "field_type": "multiline_text"}],
            },
            {
                "key": "evidence",
                "kind": "ARTIFACT",
                "name": "Nachweis",
                "create_roles": ["ADMIN", "QMB"],
                "fields": [{"key": "title", "field_type": "string", "required": True}],
            },
        ],
    }


def test_blueprint_http_validate_publish_list_and_create_root(tmp_path: Path):
    client = TestClient(build_demo_app(tmp_path))
    payload = blueprint_payload()
    validation = client.post("/container/blueprints/validate", json=payload)
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert validation.json()["deployment_order"].index("maintenance") < validation.json()["deployment_order"].index("device")

    published = client.post("/container/blueprints/publish", json=payload)
    assert published.status_code == 200
    result = published.json()
    assert result["blueprint_key"] == payload["key"]
    assert len(result["templates"]) == 3
    assert client.get("/container/blueprints").json()[0]["uid"] == result["uid"]

    root_uid = client.get("/container/workspace-root").json()["uid"]
    created = client.post(
        "/container/objects",
        json={
            "template_version_uid": result["root_template_version_uid"],
            "parent_kind": "WORKSPACE_ROOT",
            "parent_uid": root_uid,
            "values": {"serial_number": "DEV-HTTP-001"},
        },
    )
    assert created.status_code == 200
    children = client.get(f"/container/objects/{created.json()['uid']}/children")
    assert children.status_code == 200 and len(children.json()) == 1

    duplicate = client.post("/container/blueprints/publish", json=payload)
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["code"] == "container.blueprint.invalid"


def test_blueprint_http_nested_validation_is_strict(tmp_path: Path):
    client = TestClient(build_demo_app(tmp_path))
    payload = blueprint_payload()
    payload["templates"][0]["fields"][0]["field_type"] = "unknown"
    assert client.post("/container/blueprints/validate", json=payload).status_code == 422

    payload = blueprint_payload()
    payload["templates"][0]["unexpected"] = True
    assert client.post("/container/blueprints/validate", json=payload).status_code == 422

    payload = blueprint_payload()
    payload["templates"][0]["children"][0]["template_key"] = "missing"
    response = client.post("/container/blueprints/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["issues"][0]["code"] == "container.blueprint.child_template_not_found"
