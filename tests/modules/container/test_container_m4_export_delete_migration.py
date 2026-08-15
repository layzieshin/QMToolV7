from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest

from modules.container.api import (
    ActionCode, ContainerApi, ContainerError, ExternalReferenceMode,
    FieldDefinition, FieldType, ParentKind, ReferenceKind, StructuralParentRef,
    TemplateDraft, TemplateKind,
)
from modules.container.service import ContainerService
from modules.container.sqlite_repository import SQLiteContainerRepository
from modules.container.storage import FileSystemArtifactStorage
from modules.usermanagement.contracts import issue_user_context
from qm_platform.persistence.database_evolution import DatabaseEvolutionService, DatabaseSpec, MigrationStep


class EventBus:
    def __init__(self): self.events = []
    def publish(self, event): self.events.append(event)


@pytest.fixture()
def setup(tmp_path: Path):
    db = tmp_path / "container.db"
    DatabaseEvolutionService(app_home=tmp_path).migrate((DatabaseSpec("container", db, (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),)),), reason="m4")
    bus = EventBus()
    service = ContainerService(SQLiteContainerRepository(db), event_bus=bus, artifact_storage=FileSystemArtifactStorage(tmp_path / "files"))
    return ContainerApi(service), service, bus


@pytest.fixture()
def admin():
    return issue_user_context(user_id="admin", session_id="s", request_id="r", username="admin", global_roles={"ADMIN"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))


@pytest.fixture()
def qmb():
    return issue_user_context(user_id="qmb", session_id="q", request_id="q", username="qmb", global_roles={"USER"}, is_qmb=True, authenticated_at=datetime.now(timezone.utc))


def publish(api, actor, draft):
    return api.publish_template(actor, api.create_template_draft(actor, draft).uid)


def root(api):
    return StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid())


def test_export_is_deterministic_permission_complete_and_printable(setup, admin):
    api, _, bus = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",), fields=(
        FieldDefinition("serial", FieldType.STRING, printable=True),
        FieldDefinition("hidden", FieldType.STRING, printable=True, visible=False),
    )))
    obj = api.create_object(admin, template.uid, root(api), values={"serial": "=formula", "hidden": "do-not-print"})
    first = api.export_object_subtree(admin, obj.uid, include_artifacts=False, printable=True)
    second = api.export_object_subtree(admin, obj.uid, include_artifacts=False, printable=True)
    assert first.record.manifest_hash == second.record.manifest_hash
    assert first.zip_bytes == second.zip_bytes
    assert "'=formula" in first.printable_text and "do-not-print" not in first.printable_text
    with zipfile.ZipFile(BytesIO(first.zip_bytes)) as archive:
        assert json.loads(archive.read("manifest.json"))["root_object_uid"] == obj.uid
    stranger = issue_user_context(user_id="u", session_id="u", request_id="u", username="u", global_roles={"USER"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))
    with pytest.raises(ContainerError) as error:
        api.export_object_subtree(stranger, obj.uid)
    assert error.value.code == "container.authorization.denied"
    assert any(event.name == "domain.container.object.exported.v1" for event in bus.events)


def test_export_fails_closed_for_hidden_child_and_can_be_stored_finalized_signed(setup, admin):
    api, service, bus = setup
    object_template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",)))
    export_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "export", 1, ("ADMIN",)))
    parent = api.create_object(admin, object_template.uid, root(api))
    child = api.create_object(admin, object_template.uid, StructuralParentRef(ParentKind.OBJECT, parent.uid))
    with service._repository.transaction() as conn:
        conn.execute("INSERT INTO acl_entries(uid,aggregate_kind,aggregate_uid,subject_user_id,permission_code) VALUES(?,?,?,?,?)", ("only-parent", "OBJECT", parent.uid, "reader", "VIEW"))
        conn.execute("INSERT INTO acl_entries(uid,aggregate_kind,aggregate_uid,subject_user_id,permission_code) VALUES(?,?,?,?,?)", ("only-parent-update", "OBJECT", parent.uid, "reader", "CREATE_ARTIFACT"))
    reader = issue_user_context(user_id="reader", session_id="x", request_id="x", username="reader", global_roles={"USER"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))
    with pytest.raises(ContainerError) as error:
        api.export_object_subtree(reader, parent.uid)
    assert error.value.code == "container.export.incomplete_permissions"
    stored = api.store_export_as_artifact(admin, parent.uid, export_template.uid)
    artifact = api.get_artifact(admin, stored.stored_artifact_uid)
    assert artifact.revision == 2
    assert api.finalize_artifact(admin, artifact.uid, expected_revision=2).artifact_uid == artifact.uid
    assert api.sign_artifact(admin, artifact.uid, meaning="stored export").artifact_uid == artifact.uid
    assert any(reference.target_uid == artifact.uid for reference in api.list_references(admin, kind=ReferenceKind.OBJECT, uid=parent.uid))
    assert any(event.name == "domain.container.export.stored.v1" for event in bus.events)
    assert child.uid


def test_explicit_template_migration_keeps_v1_until_command_and_audits(setup, admin):
    api, service, bus = setup
    v1 = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",), fields=(FieldDefinition("serial", FieldType.STRING, required=True),)))
    obj = api.create_object(admin, v1.uid, root(api), values={"serial": "A-1"})
    v2 = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 2, ("ADMIN",), template_uid=v1.template_uid, fields=(FieldDefinition("serial", FieldType.STRING, required=True), FieldDefinition("location", FieldType.STRING, required=True))))
    assert api.get_object(admin, obj.uid).template_version_uid == v1.uid
    with pytest.raises(ContainerError) as error:
        api.migrate_object_template(admin, obj.uid, v2.uid, expected_revision=1)
    assert error.value.code == "container.template_migration.required_values"
    record = api.migrate_object_template(admin, obj.uid, v2.uid, expected_revision=1, values_for_new_required={"location": "Lab"})
    assert api.get_object(admin, obj.uid).template_version_uid == v2.uid and record.old_template_version_uid == v1.uid
    with service._repository.read() as conn:
        serial = conn.execute("SELECT string_value FROM object_field_values v JOIN field_definitions d ON d.uid=v.field_definition_uid WHERE v.object_uid=? AND d.field_key='serial'", (obj.uid,)).fetchone()[0]
    assert serial == "A-1"
    assert any(item.event_type == "object.template.migrated" and item.details for item in api.list_audit_records(admin, kind=ReferenceKind.OBJECT, uid=obj.uid))
    assert any(event.name == "domain.container.object.template_migrated.v1" for event in bus.events)
    with pytest.raises(ContainerError) as error:
        api.migrate_object_template(admin, obj.uid, v2.uid, expected_revision=2)
    assert error.value.code == "container.template_migration.same_version"


def test_physical_delete_is_policy_evidence_and_approval_guarded(setup, admin, qmb):
    api, _, bus = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "deletable", 1, ("ADMIN",)))
    obj = api.create_object(admin, template.uid, root(api))
    assert api.allowed_actions(admin, ReferenceKind.OBJECT, obj.uid)[ActionCode.PHYSICAL_DELETE].denial_code == "container.deletion.policy_required"
    policy = api.configure_deletion_policy(admin, allowed_role_codes=("ADMIN",), require_backup=True, require_second_approver=True)
    decision = api.allowed_actions(admin, ReferenceKind.OBJECT, obj.uid)[ActionCode.PHYSICAL_DELETE]
    assert not decision.allowed and decision.denial_code == "container.deletion.requires_archived"
    with pytest.raises(ContainerError) as error:
        api.physical_delete_object(admin, obj.uid, reason="retired")
    assert error.value.code == "container.deletion.requires_archived"
    archived = api.archive_object(admin, obj.uid, expected_revision=1)
    decision = api.allowed_actions(admin, ReferenceKind.OBJECT, obj.uid)[ActionCode.PHYSICAL_DELETE]
    assert decision.allowed and decision.params["require_backup"] and decision.params["require_second_approver"]
    with pytest.raises(ContainerError) as error:
        api.physical_delete_object(admin, obj.uid, reason="retired")
    assert error.value.code == "container.deletion.backup_required"
    evidence = api.create_backup_evidence(admin, scope_uid=obj.uid, integrity_hash=hashlib.sha256(b"backup").hexdigest())
    with pytest.raises(ContainerError) as error:
        api.approve_physical_deletion(admin, object_uid=obj.uid, requester_user_id=admin.user_id)
    assert error.value.code == "container.deletion.approver_must_differ"
    approval = api.approve_physical_deletion(qmb, object_uid=obj.uid, requester_user_id=admin.user_id)
    tombstone = api.physical_delete_object(admin, obj.uid, reason="retired", backup_evidence_uid=evidence.uid, approval_uid=approval.uid)
    assert tombstone.deleted_entity_uid == obj.uid and api.list_tombstones(admin)[0].uid == tombstone.uid
    assert any(event.name == "domain.container.object.physically_deleted.v1" for event in bus.events)
    assert policy.uid


def test_delete_rejects_non_empty_leaf_and_failed_mutation_publishes_no_event(setup, admin):
    api, _, bus = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",)))
    parent = api.create_object(admin, template.uid, root(api))
    api.create_object(admin, template.uid, StructuralParentRef(ParentKind.OBJECT, parent.uid))
    api.configure_deletion_policy(admin, allowed_role_codes=("ADMIN",), require_backup=False, require_second_approver=False)
    api.archive_object(admin, parent.uid, expected_revision=1)
    before = len([event for event in bus.events if event.name == "domain.container.object.physically_deleted.v1"])
    with pytest.raises(ContainerError) as error:
        api.physical_delete_object(admin, parent.uid, reason="not empty")
    assert error.value.code == "container.deletion.nonempty_leaf_unsupported"
    assert len([event for event in bus.events if event.name == "domain.container.object.physically_deleted.v1"]) == before


def test_delete_rejects_external_reference_dependency(setup, admin):
    api, _, _ = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",)))
    obj = api.create_object(admin, template.uid, root(api))
    api.create_external_reference(
        admin,
        source_kind=ReferenceKind.OBJECT,
        source_uid=obj.uid,
        provider_code="documents",
        module_code="registry",
        entity_uid="sop-1",
        mode=ExternalReferenceMode.DYNAMIC,
    )
    api.configure_deletion_policy(admin, allowed_role_codes=("ADMIN",), require_backup=False, require_second_approver=False)
    api.archive_object(admin, obj.uid, expected_revision=1)
    decision = api.allowed_actions(admin, ReferenceKind.OBJECT, obj.uid)[ActionCode.PHYSICAL_DELETE]
    assert decision.denial_code == "container.deletion.nonempty_leaf_unsupported"
    with pytest.raises(ContainerError) as error:
        api.physical_delete_object(admin, obj.uid, reason="still referenced")
    assert error.value.code == decision.denial_code


def test_delete_governance_evidence_and_approval_reject_plain_viewer(setup, admin):
    api, _, _ = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("USER",)))
    viewer = issue_user_context(
        user_id="viewer", session_id="v", request_id="v", username="viewer",
        global_roles={"USER"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc),
    )
    obj = api.create_object(viewer, template.uid, root(api))
    with pytest.raises(ContainerError) as backup_error:
        api.create_backup_evidence(viewer, scope_uid=obj.uid, integrity_hash="0" * 64)
    assert backup_error.value.code == "container.deletion.governance_denied"
    with pytest.raises(ContainerError) as approval_error:
        api.approve_physical_deletion(viewer, object_uid=obj.uid, requester_user_id=admin.user_id)
    assert approval_error.value.code == "container.deletion.governance_denied"
