from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest

from modules.container.api import ContainerApi, ContainerError, FieldDefinition, FieldType, ParentKind, StructuralParentRef, TemplateDraft, TemplateKind
from modules.container.service import ContainerService
from modules.container.sqlite_repository import SQLiteContainerRepository
from modules.container.storage import FileSystemArtifactStorage
from modules.usermanagement.contracts import issue_user_context
from qm_platform.persistence.database_evolution import DatabaseEvolutionService, DatabaseSpec, MigrationStep


class EventBus:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


@pytest.fixture()
def setup(tmp_path: Path):
    db_path = tmp_path / "container.db"
    DatabaseEvolutionService(app_home=tmp_path).migrate((DatabaseSpec("container", db_path, (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),)),), reason="test")
    events = EventBus()
    storage = FileSystemArtifactStorage(tmp_path / "artifact-storage")
    service = ContainerService(SQLiteContainerRepository(db_path), event_bus=events, artifact_storage=storage)
    return ContainerApi(service), events, service, storage, db_path


@pytest.fixture()
def admin():
    return issue_user_context(user_id="admin-id", session_id="session", request_id="request", username="admin", global_roles={"Admin"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))


def publish(api: ContainerApi, actor, draft: TemplateDraft):
    return api.publish_template(actor, api.create_template_draft(actor, draft).uid)


def owner(api: ContainerApi, actor) -> str:
    template = publish(api, actor, TemplateDraft(TemplateKind.OBJECT, "owner", 1, ("ADMIN",)))
    return api.create_object(actor, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid())).uid


def test_create_fileless_artifact_multiple_files_and_typed_values(setup, admin):
    api, events, service, _, _ = setup
    owner_uid = owner(api, admin)
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "maintenance", 1, ("ADMIN",), fields=(
        FieldDefinition("title", FieldType.STRING, required=True, historized=True),
        FieldDefinition("result", FieldType.BOOLEAN, required=True),
        FieldDefinition("date", FieldType.DATE, required=True),
    )))
    artifact = api.create_artifact(admin, artifact_template.uid, owner_uid, values={"title": "inspection", "result": True, "date": "2026-08-12"})
    assert artifact.immutable is False and api.list_artifact_files(admin, artifact.uid) == []
    first = api.add_artifact_file(admin, artifact.uid, BytesIO(b"pdf"), original_name="report.pdf", media_type="application/pdf", expected_revision=1)
    second = api.add_artifact_file(admin, artifact.uid, b"photo", original_name="photo.jpg", media_type="image/jpeg", expected_revision=2)
    assert {first.original_name, second.original_name} == {"report.pdf", "photo.jpg"}
    assert api.read_artifact_file(admin, artifact.uid, first.uid) == b"pdf"
    with service._repository.read() as conn:
        assert conn.execute("SELECT changed_by FROM artifact_field_value_history WHERE artifact_uid=?", (artifact.uid,)).fetchone()[0] == admin.user_id
    assert [event.name for event in events.events if event.name == "domain.container.artifact.created.v1"]


def test_finalization_snapshot_is_deterministic_and_blocks_mutation(setup, admin):
    api, events, service, _, _ = setup
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "maintenance", 1, ("ADMIN",), fields=(FieldDefinition("value", FieldType.INTEGER, required=True),)))
    artifact = api.create_artifact(admin, artifact_template.uid, owner(api, admin), values={"value": 7})
    file = api.add_artifact_file(admin, artifact.uid, b"evidence", original_name="evidence.txt", media_type="text/plain", expected_revision=1)
    snapshot = api.finalize_artifact(admin, artifact.uid, expected_revision=2)
    final = api.get_artifact(admin, artifact.uid)
    assert len(snapshot.state_hash) == 64 and final.immutable and final.final_snapshot_uid == snapshot.uid
    with service._repository.read() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact.uid,)).fetchone()
        files = conn.execute("SELECT * FROM artifact_files WHERE artifact_uid=? ORDER BY uid", (artifact.uid,)).fetchall()
        assert service._snapshot_hash(conn, row, files) == snapshot.state_hash
    assert api.get_artifact_file(admin, file.uid).immutable is True
    with pytest.raises(ContainerError) as error:
        api.update_artifact_fields(admin, artifact.uid, {"value": 8}, expected_revision=final.revision)
    assert error.value.code == "container.artifact.immutable"
    with pytest.raises(ContainerError) as error:
        api.add_artifact_file(admin, artifact.uid, b"later", original_name="later.txt", media_type="text/plain", expected_revision=final.revision)
    assert error.value.code == "container.artifact.immutable"
    with pytest.raises(ContainerError) as error:
        api.finalize_artifact(admin, artifact.uid, expected_revision=final.revision)
    assert error.value.code == "container.artifact.immutable"
    assert [event.name for event in events.events if event.name == "domain.container.artifact.finalized.v1"]


def test_tamper_path_metadata_and_storage_failure_are_detected(setup, admin, monkeypatch):
    api, events, service, storage, _ = setup
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "maintenance", 1, ("ADMIN",)))
    artifact = api.create_artifact(admin, artifact_template.uid, owner(api, admin))
    file = api.add_artifact_file(admin, artifact.uid, b"safe", original_name="safe.txt", media_type="text/plain", expected_revision=1)
    with pytest.raises(ContainerError) as error:
        api.add_artifact_file(admin, artifact.uid, b"bad", original_name="../escape.txt", media_type="text/plain", expected_revision=2)
    assert error.value.code == "container.storage.invalid_original_name"
    with pytest.raises(ContainerError) as error:
        api.add_artifact_file(admin, artifact.uid, b"bad", original_name="C:\\escape.txt", media_type="text/plain", expected_revision=2)
    assert error.value.code == "container.storage.invalid_original_name"
    with service._repository.read() as conn:
        path = conn.execute("SELECT relative_path FROM artifact_files WHERE uid=?", (file.uid,)).fetchone()[0]
    (storage._root_path / path).write_bytes(b"tampered")
    with pytest.raises(ContainerError) as error:
        api.read_artifact_file(admin, artifact.uid, file.uid)
    assert error.value.code == "container.storage.integrity_failed"
    assert not [event for event in events.events if event.name == "domain.container.artifact.finalized.v1"]


def test_storage_and_database_failures_compensate_files_and_events(setup, admin, monkeypatch):
    api, events, service, storage, _ = setup
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "maintenance", 1, ("ADMIN",)))
    artifact = api.create_artifact(admin, artifact_template.uid, owner(api, admin))
    before = set(storage._root_path.rglob("*.blob"))
    def fail_audit(*args, **kwargs):
        raise RuntimeError("db failure after storage")
    monkeypatch.setattr(service, "_audit", fail_audit)
    with pytest.raises(RuntimeError):
        api.add_artifact_file(admin, artifact.uid, b"will rollback", original_name="rollback.txt", media_type="text/plain", expected_revision=1)
    assert set(storage._root_path.rglob("*.blob")) == before
    assert not [event for event in events.events if event.name == "domain.container.artifact.file_added.v1"]


def test_storage_failure_rolls_back_without_event(setup, admin, monkeypatch):
    api, events, service, _, _ = setup
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "maintenance", 1, ("ADMIN",)))
    artifact = api.create_artifact(admin, artifact_template.uid, owner(api, admin))
    def fail_store(*args, **kwargs):
        raise ContainerError("container.storage.write_failed")
    monkeypatch.setattr(service._artifact_storage, "store", fail_store)
    with pytest.raises(ContainerError) as error:
        api.add_artifact_file(admin, artifact.uid, b"unwritten", original_name="unwritten.txt", media_type="text/plain", expected_revision=1)
    assert error.value.code == "container.storage.write_failed"
    assert api.get_artifact(admin, artifact.uid).revision == 1
    assert not [event for event in events.events if event.name == "domain.container.artifact.file_added.v1"]


def test_signature_and_correction_copy_files_without_changing_original(setup, admin):
    api, _, _, _, _ = setup
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "maintenance", 1, ("ADMIN",), fields=(FieldDefinition("note", FieldType.STRING),)))
    artifact = api.create_artifact(admin, artifact_template.uid, owner(api, admin), values={"note": "original"})
    original_file = api.add_artifact_file(admin, artifact.uid, b"copy me", original_name="copy.txt", media_type="text/plain", expected_revision=1)
    snapshot = api.finalize_artifact(admin, artifact.uid, expected_revision=2)
    signature = api.sign_artifact(admin, artifact.uid, meaning="reviewed")
    assert signature.snapshot_uid == snapshot.uid and signature.state_hash == snapshot.state_hash
    with pytest.raises(ContainerError) as error:
        api.sign_artifact(admin, artifact.uid, meaning="again")
    assert error.value.code == "container.signature.duplicate"
    corrected = api.correct_artifact(admin, artifact.uid)
    assert corrected.uid != artifact.uid and not corrected.immutable
    assert api.correction_source_uid(admin, corrected.uid) == artifact.uid
    copied_file = api.list_artifact_files(admin, corrected.uid)[0]
    assert copied_file.uid != original_file.uid and copied_file.content_hash == original_file.content_hash
    assert api.read_artifact_file(admin, corrected.uid, copied_file.uid) == b"copy me"
    assert api.get_artifact(admin, artifact.uid).immutable is True


def test_artifact_reference_requires_existing_artifact_and_role_revision_are_checked(setup, admin):
    api, _, _, _, _ = setup
    owner_uid = owner(api, admin)
    target_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "target", 1, ("ADMIN",)))
    target = api.create_artifact(admin, target_template.uid, owner_uid)
    source_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "source", 1, ("ADMIN",), fields=(FieldDefinition("target", FieldType.ARTIFACT_REFERENCE, required=True),)))
    with pytest.raises(ContainerError) as error:
        api.create_artifact(admin, source_template.uid, owner_uid, values={"target": "missing"})
    assert error.value.code == "container.field.reference_not_found"
    source = api.create_artifact(admin, source_template.uid, owner_uid, values={"target": target.uid})
    with pytest.raises(ContainerError) as error:
        api.update_artifact_fields(admin, source.uid, {"target": target.uid}, expected_revision=999)
    assert error.value.code == "container.revision.conflict"
    user = issue_user_context(user_id="user", session_id="s", request_id="r", username="u", global_roles={"USER"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))
    with pytest.raises(ContainerError) as error:
        api.create_artifact(user, target_template.uid, owner_uid)
    assert error.value.code == "container.authorization.denied"
