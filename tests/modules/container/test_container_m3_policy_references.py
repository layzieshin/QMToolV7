from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.container.api import (
    ActionCode, ChildMode, ContainerApi, ContainerError, ExternalReferenceMode,
    FieldDefinition, FieldType, LifecycleStateDefinition,
    LifecycleTransitionDefinition, ParentKind, ReferenceKind, StructuralParentRef,
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


class Resolver:
    def resolve(self, *, provider_code: str, module_code: str, entity_uid: str) -> str:
        assert (provider_code, module_code, entity_uid) == ("docs", "registry", "external")
        return "released-v2"


@pytest.fixture()
def setup(tmp_path: Path):
    db = tmp_path / "container.db"
    DatabaseEvolutionService(app_home=tmp_path).migrate((DatabaseSpec("container", db, (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),)),), reason="m3")
    service = ContainerService(SQLiteContainerRepository(db), event_bus=EventBus(), artifact_storage=FileSystemArtifactStorage(tmp_path / "artifacts"), external_reference_resolver=Resolver())
    return ContainerApi(service), service


@pytest.fixture()
def admin():
    return issue_user_context(user_id="admin", session_id="s", request_id="r", username="admin", global_roles={"ADMIN"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))


def publish(api, actor, draft):
    return api.publish_template(actor, api.create_template_draft(actor, draft).uid)


def test_references_are_canonical_visible_and_physical_delete_is_decision_point(setup, admin):
    api, _ = setup
    object_template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",)))
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "record", 1, ("ADMIN",)))
    root = StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid())
    first, second = api.create_object(admin, object_template.uid, root), api.create_object(admin, object_template.uid, root)
    artifact = api.create_artifact(admin, artifact_template.uid, first.uid)
    link = api.create_link_type(admin, code="uses", source_kind=ReferenceKind.OBJECT, target_kind=ReferenceKind.ARTIFACT)
    reference = api.create_reference(admin, source_kind=ReferenceKind.ARTIFACT, source_uid=artifact.uid, target_kind=ReferenceKind.OBJECT, target_uid=second.uid, link_type_uid=link.uid)
    assert reference.source_kind is ReferenceKind.OBJECT and reference.source_uid == second.uid and reference.target_uid == artifact.uid
    assert api.list_references(admin, kind=ReferenceKind.ARTIFACT, uid=artifact.uid)[0].uid == reference.uid
    with pytest.raises(ContainerError) as error:
        api.create_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=second.uid, target_kind=ReferenceKind.ARTIFACT, target_uid=artifact.uid, link_type_uid=link.uid)
    assert error.value.code == "container.reference.duplicate"
    assert api.allowed_actions(admin, ReferenceKind.OBJECT, second.uid)[ActionCode.PHYSICAL_DELETE].denial_code == "container.deletion.policy_required"


def test_external_reference_lifecycle_signature_archive_and_search(setup, admin):
    api, _ = setup
    draft = TemplateDraft(
        TemplateKind.OBJECT, "asset", 1, ("ADMIN",),
        fields=(FieldDefinition("label", FieldType.STRING, searchable=True),),
        initial_state="ACTIVE",
        lifecycle_states=(LifecycleStateDefinition("ACTIVE", True), LifecycleStateDefinition("OUT_OF_SERVICE")),
        lifecycle_transitions=(LifecycleTransitionDefinition("ACTIVE", "OUT_OF_SERVICE", ("QMB",), reason_required=True, signature_required=True),),
    )
    template = publish(api, admin, draft)
    obj = api.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()), values={"label": "Ärger #42"})
    fixed = api.create_external_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=obj.uid, provider_code="docs", module_code="registry", entity_uid="external", mode=ExternalReferenceMode.FIXED, fixed_version_uid="v1")
    assert api.resolve_external_reference(admin, fixed.uid) == "v1"
    dynamic = api.create_external_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=obj.uid, provider_code="docs", module_code="registry", entity_uid="external", mode=ExternalReferenceMode.DYNAMIC)
    assert api.resolve_external_reference(admin, dynamic.uid) == "released-v2"
    assert api.list_external_reference_resolutions(admin, dynamic.uid)[0].resolved_by == admin.user_id
    assert api.search_objects(admin, "Ärger", field_keys=("label",))[0].uid == obj.uid
    with pytest.raises(ContainerError) as error:
        api.transition_object(admin, obj.uid, to_state="OUT_OF_SERVICE", reason="", expected_revision=1, signature_meaning="review")
    assert error.value.code == "container.lifecycle.role_denied"
    qmb = issue_user_context(user_id="qmb", session_id="s2", request_id="r2", username="qmb", global_roles={"USER"}, is_qmb=True, authenticated_at=datetime.now(timezone.utc))
    transitioned = api.transition_object(qmb, obj.uid, to_state="OUT_OF_SERVICE", reason="Defekt", expected_revision=1, signature_meaning="freigegeben")
    assert transitioned.state == "OUT_OF_SERVICE"
    archived = api.archive_object(admin, obj.uid, expected_revision=2)
    assert archived.archived
    with pytest.raises(ContainerError) as error:
        api.update_object_fields(admin, obj.uid, {"label": "neu"}, expected_revision=3)
    assert error.value.code == "container.archive.read_only"
    assert api.reactivate_object(admin, obj.uid, expected_revision=3).archived is False
    signature = api.list_object_signatures(qmb, obj.uid)[0]
    assert api.get_object_snapshot(qmb, signature.snapshot_uid).state_hash == signature.state_hash


def test_read_requires_confirmed_actor_and_search_is_permission_filtered(setup, admin):
    api, _ = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",), fields=(FieldDefinition("label", FieldType.STRING, searchable=True),)))
    obj = api.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()), values={"label": "secret"})
    with pytest.raises(ContainerError) as error:
        api.get_object(object(), obj.uid)
    assert error.value.code == "container.authorization.confirmed_actor_required"
    stranger = issue_user_context(user_id="stranger", session_id="x", request_id="x", username="stranger", global_roles={"USER"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))
    with pytest.raises(ContainerError) as error:
        api.get_object(stranger, obj.uid)
    assert error.value.code == "container.authorization.denied"
    assert api.search_objects(stranger, "secret") == []


def test_external_reference_validation_and_missing_resolver(tmp_path: Path, admin):
    db = tmp_path / "missing-resolver.db"
    DatabaseEvolutionService(app_home=tmp_path).migrate((DatabaseSpec("container", db, (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),)),), reason="m3")
    api = ContainerApi(ContainerService(SQLiteContainerRepository(db), event_bus=EventBus()))
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",)))
    obj = api.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()))
    with pytest.raises(ContainerError) as error:
        api.create_external_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=obj.uid, provider_code="docs", module_code="registry", entity_uid="external", mode=ExternalReferenceMode.FIXED)
    assert error.value.code == "container.external_reference.fixed_version_required"
    with pytest.raises(ContainerError) as error:
        api.create_external_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=obj.uid, provider_code="docs", module_code="registry", entity_uid="external", mode=ExternalReferenceMode.FIXED, fixed_version_uid="latest")
    assert error.value.code == "container.external_reference.fixed_version_required"
    dynamic = api.create_external_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=obj.uid, provider_code="docs", module_code="registry", entity_uid="external", mode=ExternalReferenceMode.DYNAMIC)
    with pytest.raises(ContainerError) as error:
        api.resolve_external_reference(admin, dynamic.uid)
    assert error.value.code == "container.external_reference.resolver_unavailable"


def test_reference_variants_move_and_correction_are_publicly_visible(setup, admin):
    api, _ = setup
    root = StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid())
    object_template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",)))
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "record", 1, ("ADMIN",)))
    one, two = api.create_object(admin, object_template.uid, root), api.create_object(admin, object_template.uid, root)
    left, right = api.create_artifact(admin, artifact_template.uid, one.uid), api.create_artifact(admin, artifact_template.uid, one.uid)
    oo = api.create_link_type(admin, code="related", source_kind=ReferenceKind.OBJECT, target_kind=ReferenceKind.OBJECT)
    aa = api.create_link_type(admin, code="derived", source_kind=ReferenceKind.ARTIFACT, target_kind=ReferenceKind.ARTIFACT)
    assert api.create_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=one.uid, target_kind=ReferenceKind.OBJECT, target_uid=two.uid, link_type_uid=oo.uid).uid
    assert api.create_reference(admin, source_kind=ReferenceKind.ARTIFACT, source_uid=left.uid, target_kind=ReferenceKind.ARTIFACT, target_uid=right.uid, link_type_uid=aa.uid).uid
    with pytest.raises(ContainerError) as error:
        api.create_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid="missing", target_kind=ReferenceKind.OBJECT, target_uid=two.uid, link_type_uid=oo.uid)
    assert error.value.code == "container.reference.target_not_found"
    with pytest.raises(ContainerError) as error:
        api.create_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=one.uid, target_kind=ReferenceKind.ARTIFACT, target_uid=left.uid, link_type_uid=oo.uid)
    assert error.value.code == "container.reference.kind_mismatch"
    assert api.move_object(admin, two.uid, StructuralParentRef(ParentKind.OBJECT, one.uid), expected_revision=1).uid == two.uid
    assert api.list_references(admin, kind=ReferenceKind.OBJECT, uid=two.uid)[0].target_uid == two.uid
    finalized = api.finalize_artifact(admin, left.uid, expected_revision=1)
    corrected = api.correct_artifact(admin, left.uid)
    assert finalized.uid and any(r.target_uid == left.uid for r in api.list_references(admin, kind=ReferenceKind.ARTIFACT, uid=corrected.uid))
    assert api.correction_source_uid(admin, corrected.uid) == left.uid


def test_lifecycle_negative_signatures_and_event_after_commit(tmp_path: Path, admin):
    db, bus = tmp_path / "lifecycle.db", EventBus()
    DatabaseEvolutionService(app_home=tmp_path).migrate((DatabaseSpec("container", db, (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),)),), reason="m3")
    api = ContainerApi(ContainerService(SQLiteContainerRepository(db), event_bus=bus))
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",), fields=(FieldDefinition("label", FieldType.STRING),), lifecycle_states=(LifecycleStateDefinition("ACTIVE", True), LifecycleStateDefinition("RETIRED")), lifecycle_transitions=(LifecycleTransitionDefinition("ACTIVE", "RETIRED", ("QMB",), True, True),)))
    obj = api.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()), values={"label": "before"})
    qmb = issue_user_context(user_id="qmb", session_id="q", request_id="q", username="qmb", global_roles={"USER"}, is_qmb=True, authenticated_at=datetime.now(timezone.utc))
    for reason, meaning, code in (("", "ok", "container.lifecycle.reason_required"), ("because", None, "container.lifecycle.signature_required")):
        with pytest.raises(ContainerError) as error:
            api.transition_object(qmb, obj.uid, to_state="RETIRED", reason=reason, expected_revision=1, signature_meaning=meaning)
        assert error.value.code == code
    with pytest.raises(ContainerError) as error:
        api.transition_object(qmb, obj.uid, to_state="ACTIVE", reason="because", expected_revision=1, signature_meaning="ok")
    assert error.value.code == "container.lifecycle.invalid_transition"
    transitioned = api.transition_object(qmb, obj.uid, to_state="RETIRED", reason="because", expected_revision=1, signature_meaning="ok")
    signature = api.list_object_signatures(qmb, obj.uid)[0]
    snapshot = api.get_object_snapshot(qmb, signature.snapshot_uid)
    assert transitioned.state == "RETIRED" and snapshot.revision == 2 and any(event.name == "domain.container.object.transitioned.v1" for event in bus.events)
    api.update_object_fields(qmb, obj.uid, {"label": "after"}, expected_revision=2)
    assert api.get_object_snapshot(qmb, signature.snapshot_uid).state_hash == snapshot.state_hash


def test_archive_subtree_search_pagination_and_decisions(setup, admin):
    api, _ = setup
    template = publish(api, admin, TemplateDraft(TemplateKind.OBJECT, "asset", 1, ("ADMIN",), fields=(FieldDefinition("serial", FieldType.STRING, searchable=True), FieldDefinition("hidden", FieldType.STRING)), lifecycle_states=(LifecycleStateDefinition("ACTIVE", True), LifecycleStateDefinition("DONE",)), lifecycle_transitions=(LifecycleTransitionDefinition("ACTIVE", "DONE", ("ADMIN",)),)))
    artifact_template = publish(api, admin, TemplateDraft(TemplateKind.ARTIFACT, "record", 1, ("ADMIN",)))
    root = StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid())
    parent = api.create_object(admin, template.uid, root, values={"serial": "A#1"})
    child = api.create_object(admin, template.uid, StructuralParentRef(ParentKind.OBJECT, parent.uid), values={"serial": "A#2"})
    artifact = api.create_artifact(admin, artifact_template.uid, child.uid)
    linked = api.create_link_type(admin, code="contains", source_kind=ReferenceKind.OBJECT, target_kind=ReferenceKind.ARTIFACT)
    api.create_reference(admin, source_kind=ReferenceKind.OBJECT, source_uid=child.uid, target_kind=ReferenceKind.ARTIFACT, target_uid=artifact.uid, link_type_uid=linked.uid)
    assert [item.uid for item in api.search_objects(admin, "A#", limit=1, offset=0)] == sorted([parent.uid, child.uid])[:1]
    for kwargs in ({"field_keys": ("hidden",)}, {"field_keys": ("unknown",)}, {"limit": 101}, {"offset": -1}):
        with pytest.raises(ContainerError): api.search_objects(admin, "A", **kwargs)
    api.archive_object(admin, parent.uid, expected_revision=1)
    assert api.search_objects(admin, "A#") == [] and {item.uid for item in api.search_objects(admin, "A#", include_archived=True)} == {parent.uid, child.uid}
    for operation in (
        lambda: api.update_object_fields(admin, child.uid, {"serial": "no"}, expected_revision=2),
        lambda: api.create_object(admin, template.uid, StructuralParentRef(ParentKind.OBJECT, child.uid), values={"serial": "new"}),
        lambda: api.create_artifact(admin, artifact_template.uid, child.uid),
        lambda: api.move_object(admin, child.uid, root, expected_revision=2),
        lambda: api.transition_object(admin, child.uid, to_state="DONE", reason=None, expected_revision=2),
    ):
        with pytest.raises(ContainerError) as error: operation()
        assert error.value.code == "container.archive.read_only"
    assert api.list_references(admin, kind=ReferenceKind.ARTIFACT, uid=artifact.uid)
    assert api.reactivate_object(admin, parent.uid, expected_revision=2).archived is False
    assert api.get_object(admin, child.uid).archived is False
    stranger = issue_user_context(user_id="s", session_id="s", request_id="s", username="s", global_roles={"USER"}, is_qmb=False, authenticated_at=datetime.now(timezone.utc))
    decision = api.allowed_actions(stranger, ReferenceKind.OBJECT, parent.uid)
    assert decision[ActionCode.VIEW].denial_code == decision[ActionCode.UPDATE].denial_code == "container.authorization.denied"
    with pytest.raises(ContainerError) as error: api.update_object_fields(stranger, parent.uid, {"serial": "forged"}, expected_revision=3)
    assert error.value.code == decision[ActionCode.UPDATE].denial_code


def test_search_normalizes_typed_searchable_values(setup, admin):
    api, _ = setup
    template = publish(api, admin, TemplateDraft(
        TemplateKind.OBJECT,
        "measured",
        1,
        ("ADMIN",),
        fields=(FieldDefinition("count", FieldType.INTEGER, searchable=True),),
    ))
    obj = api.create_object(admin, template.uid, StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()), values={"count": 4711})
    assert [item.uid for item in api.search_objects(admin, "4711", field_keys=("count",))] == [obj.uid]
