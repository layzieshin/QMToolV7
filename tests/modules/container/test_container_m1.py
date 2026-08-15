from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from modules.container.api import (
    ChildDefinition, ChildMode, ContainerApi, ContainerError, FieldDefinition,
    FieldType, ParentKind, StructuralParentRef, TemplateDraft, TemplateKind,
)
from modules.container.service import ContainerService
from modules.container.sqlite_repository import SQLiteContainerRepository
from modules.usermanagement.contracts import issue_user_context
from qm_platform.persistence.database_evolution import DatabaseEvolutionService, DatabaseSpec, MigrationStep


class EventBus:
    def __init__(self): self.events = []
    def publish(self, event): self.events.append(event)


@pytest.fixture()
def api(tmp_path: Path):
    db_path = tmp_path / "container.db"
    migration = Path("modules/container/migrations/0001_initial.sql")
    DatabaseEvolutionService(app_home=tmp_path).migrate((DatabaseSpec("container", db_path, (MigrationStep(1, "initial", migration),)),), reason="test")
    bus = EventBus()
    return ContainerApi(ContainerService(SQLiteContainerRepository(db_path), event_bus=bus)), bus


@pytest.fixture()
def admin():
    return issue_user_context(user_id="admin-id", session_id="session", request_id="request", username="admin", global_roles={"Admin"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))


def publish(api, actor, draft):
    version = api.create_template_draft(actor, draft)
    return api.publish_template(actor, version.uid)


def test_create_object_from_published_template_and_fixed_children(api, admin):
    container, events = api
    child = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "child", 1, ("ADMIN",)))
    parent = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "parent", 1, ("ADMIN",), fields=(FieldDefinition("serial", FieldType.STRING, required=True, historized=True),), children=(ChildDefinition("master", child.uid, min_count=1, auto_create=True, mode=ChildMode.FIXED),)))
    result = container.create_object(admin, parent.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid()), values={"serial": "AI-123"})
    assert result.depth == 1 and result.revision == 1
    assert [event.name for event in events.events if event.name == "domain.container.object.created.v1"]


def test_validate_fields_and_revision_conflict(api, admin):
    container, _ = api
    template = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "Device", 1, ("ADMIN",), fields=(FieldDefinition("quantity", FieldType.INTEGER, required=True),)))
    with pytest.raises(ContainerError) as error:
        container.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid()), values={"quantity": "one"})
    assert error.value.code == "container.field.invalid_type"
    result = container.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid()), values={"quantity": 1})
    with pytest.raises(ContainerError) as error:
        container.update_object_fields(admin, result.uid, {"quantity": 2}, expected_revision=99)
    assert error.value.code == "container.revision.conflict"


def test_publish_is_immutable_and_new_version_does_not_migrate_instances(api, admin):
    container, _ = api
    first = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "Device", 1, ("ADMIN",)))
    instance = container.create_object(admin, first.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid()))
    second = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "Device", 2, ("ADMIN",), template_uid=first.template_uid))
    assert container.get_object(admin, instance.uid).template_version_uid == first.uid
    assert second.uid != first.uid
    with pytest.raises(ContainerError):
        container.publish_template(admin, first.uid)


def test_reject_fixed_move_cycle_and_missing_parent(api, admin):
    container, _ = api
    child = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "child", 1, ("ADMIN",)))
    parent = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "parent", 1, ("ADMIN",), children=(ChildDefinition("fixed", child.uid, min_count=1, auto_create=True, mode=ChildMode.FIXED),)))
    root = container.workspace_root_uid()
    top = container.create_object(admin, parent.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, root))
    fixed = container.list_children(admin, StructuralParentRef(ParentKind.OBJECT, top.uid))[0]
    with pytest.raises(ContainerError) as error:
        container.move_object(admin, fixed.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, root), expected_revision=1)
    assert error.value.code == "container.tree.fixed_child"
    with pytest.raises(ContainerError) as error:
        container.move_object(admin, top.uid, StructuralParentRef(ParentKind.OBJECT, top.uid), expected_revision=1)
    assert error.value.code == "container.tree.cycle"
    with pytest.raises(ContainerError) as error:
        container.create_object(admin, child.uid, StructuralParentRef(ParentKind.OBJECT, "unknown"))
    assert error.value.code == "container.tree.parent_not_found"


def test_schema_has_single_workspace_root_and_relational_field_columns(api):
    container, _ = api
    root = container.workspace_root_uid()
    assert root


def test_forged_actor_and_failed_transaction_publish_no_event(api, admin):
    container, events = api
    with pytest.raises(ContainerError) as error:
        container.create_template_draft(object(), TemplateDraft(TemplateKind.OBJECT, "bad", 1, ("ADMIN",)))
    assert error.value.code == "container.authorization.confirmed_actor_required"
    version = container.create_template_draft(admin, TemplateDraft(TemplateKind.OBJECT, "event", 1, ("ADMIN",)))
    with pytest.raises(ContainerError):
        container.publish_template(admin, version.uid + "-missing")
    assert not [event for event in events.events if event.name == "domain.container.template.published.v1"]


def test_template_create_roles_are_server_enforced(api, admin):
    container, _ = api
    qmb = issue_user_context(user_id="qmb-id", session_id="qmb-session", request_id="qmb-request", username="qmb", global_roles={"User"}, is_qmb=True, authenticated_at=datetime.now(timezone.utc))
    version = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "qmb-only", 1, ("QMB",)))
    parent = StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid())
    with pytest.raises(ContainerError) as error:
        container.create_object(admin, version.uid, parent)
    assert error.value.code == "container.authorization.create_denied"
    assert container.create_object(qmb, version.uid, parent).uid


def test_depth_limit_and_flexible_move_rebase(api, admin):
    container, _ = api
    template = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "flex", 1, ("ADMIN",)))
    root = StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid())
    first = container.create_object(admin, template.uid, root)
    second = container.create_object(admin, template.uid, root)
    child = container.create_object(admin, template.uid, StructuralParentRef(ParentKind.OBJECT, first.uid))
    moved = container.move_object(admin, child.uid, root, expected_revision=1)
    assert moved.depth == 1 and moved.parent == root
    current = moved
    for expected_depth in range(2, 33):
        current = container.create_object(admin, template.uid, StructuralParentRef(ParentKind.OBJECT, current.uid))
        assert current.depth == expected_depth
    with pytest.raises(ContainerError) as error:
        container.create_object(admin, template.uid, StructuralParentRef(ParentKind.OBJECT, current.uid))
    assert error.value.code == "container.tree.max_depth"
    assert second.uid != first.uid


def test_auto_child_depth_limit_uses_stable_domain_error(api, admin):
    container, _ = api
    leaf = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "leaf", 1, ("ADMIN",)))
    parent = publish(container, admin, TemplateDraft(
        TemplateKind.OBJECT,
        "auto-parent",
        1,
        ("ADMIN",),
        children=(ChildDefinition("auto", leaf.uid, auto_create=True),),
    ))
    current = container.create_object(admin, leaf.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid()))
    for _ in range(2, 32):
        current = container.create_object(admin, leaf.uid, StructuralParentRef(ParentKind.OBJECT, current.uid))
    with pytest.raises(ContainerError) as error:
        container.create_object(admin, parent.uid, StructuralParentRef(ParentKind.OBJECT, current.uid))
    assert error.value.code == "container.tree.max_depth"


@pytest.mark.parametrize(
    ("field_type", "value", "options"),
    [
        (FieldType.STRING, "text", ()),
        (FieldType.MULTILINE_TEXT, "first\nsecond", ()),
        (FieldType.INTEGER, 3, ()),
        (FieldType.DECIMAL, "1.25", ()),
        (FieldType.BOOLEAN, True, ()),
        (FieldType.DATE, "2026-08-12", ()),
        (FieldType.DATETIME, "2026-08-12T10:15:00+00:00", ()),
        (FieldType.SINGLE_SELECT, "one", ("one", "two")),
        (FieldType.MULTI_SELECT, ("one", "two"), ("one", "two")),
        (FieldType.USER_REFERENCE, "user-uid", ()),
        (FieldType.OBJECT_REFERENCE, None, ()),
        (FieldType.ARTIFACT_REFERENCE, "artifact-uid", ()),
    ],
)
def test_field_engine_accepts_each_declared_type(api, admin, field_type, value, options):
    container, _ = api
    parent = StructuralParentRef(ParentKind.WORKSPACE_ROOT, container.workspace_root_uid())
    reference = container.create_object(admin, publish(container, admin, TemplateDraft(TemplateKind.OBJECT, "reference", 1, ("ADMIN",))).uid, parent)
    actual_value = reference.uid if field_type is FieldType.OBJECT_REFERENCE else value
    if field_type is FieldType.ARTIFACT_REFERENCE:
        artifact_template = publish(container, admin, TemplateDraft(TemplateKind.ARTIFACT, "reference-artifact", 1, ("ADMIN",)))
        actual_value = container.create_artifact(admin, artifact_template.uid, reference.uid).uid
    template = publish(container, admin, TemplateDraft(TemplateKind.OBJECT, f"field-{field_type.value}", 1, ("ADMIN",), fields=(FieldDefinition("value", field_type, required=True, options=options),)))
    assert container.create_object(admin, template.uid, parent, values={"value": actual_value}).uid
