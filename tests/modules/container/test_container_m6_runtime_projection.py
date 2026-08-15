from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.container.api import (
    BlueprintTemplateDraft,
    ContainerApi,
    ContainerError,
    FieldDefinition,
    FieldType,
    LifecycleStateDefinition,
    LifecycleTransitionDefinition,
    ModuleBlueprintDraft,
    ParentKind,
    StructuralParentRef,
    TemplateKind,
)
from modules.container.service import ContainerService
from modules.container.sqlite_repository import SQLiteContainerRepository
from modules.container.storage import FileSystemArtifactStorage
from modules.usermanagement.contracts import issue_user_context
from qm_platform.persistence.database_evolution import DatabaseEvolutionService, DatabaseSpec, MigrationStep


class EventBus:
    def publish(self, event):
        return None


def actor(user_id: str, *roles: str, is_qmb: bool = False):
    return issue_user_context(
        user_id=user_id,
        session_id=f"session-{user_id}",
        request_id=f"request-{user_id}",
        username=user_id,
        global_roles=roles,
        is_qmb=is_qmb,
        authenticated_at=datetime.now(timezone.utc),
    )


@pytest.fixture()
def api(tmp_path: Path) -> ContainerApi:
    database = tmp_path / "container.db"
    DatabaseEvolutionService(app_home=tmp_path).migrate(
        (
            DatabaseSpec(
                "container",
                database,
                (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),),
            ),
        ),
        reason="runtime-projection-test",
    )
    return ContainerApi(
        ContainerService(
            SQLiteContainerRepository(database),
            event_bus=EventBus(),
            artifact_storage=FileSystemArtifactStorage(tmp_path / "artifacts"),
        )
    )


def user_module(
    *,
    key: str = "inspections",
    create_roles: tuple[str, ...] = ("USER",),
    hidden_required: bool = False,
):
    root = BlueprintTemplateDraft(
        key="inspection",
        kind=TemplateKind.OBJECT,
        name="Prüfung",
        create_roles=create_roles,
        fields=(
            FieldDefinition("title", FieldType.STRING, required=True, searchable=True),
            FieldDefinition("internal_note", FieldType.STRING, required=hidden_required, visible=False),
            FieldDefinition("priority", FieldType.SINGLE_SELECT, options=("normal", "hoch")),
        ),
        initial_state="DRAFT",
        lifecycle_states=(
            LifecycleStateDefinition("DRAFT", initial=True),
            LifecycleStateDefinition("REVIEW"),
            LifecycleStateDefinition("APPROVED"),
        ),
        lifecycle_transitions=(
            LifecycleTransitionDefinition("DRAFT", "REVIEW", allowed_roles=("USER",), reason_required=True),
            LifecycleTransitionDefinition("REVIEW", "APPROVED", allowed_roles=("QMB",), signature_required=True),
        ),
    )
    evidence = BlueprintTemplateDraft(
        key="evidence",
        kind=TemplateKind.ARTIFACT,
        name="Nachweis",
        create_roles=create_roles,
        fields=(FieldDefinition("title", FieldType.STRING, required=True),),
    )
    return ModuleBlueprintDraft(
        key=key,
        name="Prüfungen",
        description="Prüfungen mit Nachweisen",
        root_template_key="inspection",
        templates=(root, evidence),
    )


def test_runtime_projection_is_actor_filtered_and_supports_object_artifacts(api: ContainerApi):
    admin = actor("admin", "ADMIN")
    user = actor("user", "USER")
    published = api.publish_module_blueprint(admin, user_module())
    api.publish_module_blueprint(admin, user_module(key="administration", create_roles=("ADMIN",)))

    initial = api.list_runtime_modules(user)
    assert [module.blueprint_key for module in initial] == ["inspections"]
    root_template = next(template for template in initial[0].templates if template.is_root)
    assert root_template.create_allowed is True
    assert [field.key for field in root_template.fields] == ["title", "priority"]
    assert root_template.fields[1].options == ("normal", "hoch")
    assert [(item.from_state, item.to_state) for item in root_template.lifecycle_transitions] == [
        ("DRAFT", "REVIEW")
    ]
    assert not hasattr(root_template.lifecycle_transitions[0], "allowed_roles")

    created = api.create_object(
        user,
        published.root_template_version_uid,
        StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()),
        values={"title": "Wareneingangsprüfung", "priority": "hoch"},
    )
    artifact_template = next(template for template in published.templates if template.template_key == "evidence")
    artifact = api.create_artifact(
        user,
        artifact_template.template_version_uid,
        created.uid,
        values={"title": "Messprotokoll"},
    )

    projected = api.list_runtime_modules(user)[0]
    assert [item.uid for item in projected.root_objects] == [created.uid]
    detail = api.get_object_detail(user, created.uid)
    assert detail.field_values == {"priority": "hoch", "title": "Wareneingangsprüfung"}
    assert [item.uid for item in detail.artifacts] == [artifact.uid]


def test_runtime_projection_requires_a_confirmed_actor(api: ContainerApi):
    with pytest.raises(ContainerError) as error:
        api.list_runtime_modules(object())
    assert error.value.code == "container.authorization.confirmed_actor_required"


def test_runtime_projection_does_not_offer_an_unrenderable_hidden_required_field(api: ContainerApi):
    admin = actor("admin", "ADMIN")
    user = actor("user", "USER")
    published = api.publish_module_blueprint(admin, user_module(key="hidden-required", hidden_required=True))
    created = api.create_object(
        user,
        published.root_template_version_uid,
        StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()),
        values={"title": "Bestehender Eintrag", "internal_note": "serverseitig gesetzt"},
    )

    projected = api.list_runtime_modules(user)[0]
    root_template = next(template for template in projected.templates if template.is_root)
    assert root_template.create_allowed is False
    assert [field.key for field in root_template.fields] == ["title", "priority"]
    assert [item.uid for item in projected.root_objects] == [created.uid]
