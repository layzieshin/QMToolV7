from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.container.api import (
    BlueprintChildDefinition,
    BlueprintTemplateDraft,
    ChildMode,
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
    TemplateState,
)
from modules.container.service import ContainerService
from modules.container.sqlite_repository import SQLiteContainerRepository
from modules.container.storage import FileSystemArtifactStorage
from modules.usermanagement.contracts import issue_user_context
from qm_platform.persistence.database_evolution import (
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)


class EventBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


@pytest.fixture()
def setup(tmp_path: Path):
    database = tmp_path / "container.db"
    DatabaseEvolutionService(app_home=tmp_path).migrate(
        (
            DatabaseSpec(
                "container",
                database,
                (MigrationStep(1, "initial", Path("modules/container/migrations/0001_initial.sql")),),
            ),
        ),
        reason="blueprint-test",
    )
    events = EventBus()
    api = ContainerApi(
        ContainerService(
            SQLiteContainerRepository(database),
            event_bus=events,
            artifact_storage=FileSystemArtifactStorage(tmp_path / "artifacts"),
        )
    )
    return api, events


@pytest.fixture()
def admin():
    return issue_user_context(
        user_id="admin",
        session_id="session",
        request_id="request",
        username="admin",
        global_roles={"ADMIN"},
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )


def device_blueprint(*, key: str = "device-management") -> ModuleBlueprintDraft:
    maintenance = BlueprintTemplateDraft(
        key="maintenance",
        kind=TemplateKind.OBJECT,
        name="Wartung",
        create_roles=("ADMIN", "QMB"),
        fields=(FieldDefinition("note", FieldType.MULTILINE_TEXT, printable=True),),
    )
    evidence = BlueprintTemplateDraft(
        key="evidence",
        kind=TemplateKind.ARTIFACT,
        name="Nachweis",
        create_roles=("ADMIN", "QMB"),
        fields=(FieldDefinition("title", FieldType.STRING, required=True, printable=True),),
    )
    device = BlueprintTemplateDraft(
        key="device",
        kind=TemplateKind.OBJECT,
        name="Gerät",
        create_roles=("ADMIN", "QMB"),
        fields=(
            FieldDefinition(
                "serial_number",
                FieldType.STRING,
                required=True,
                searchable=True,
                printable=True,
            ),
        ),
        children=(
            BlueprintChildDefinition(
                "maintenance",
                "maintenance",
                min_count=1,
                max_count=1,
                auto_create=True,
                mode=ChildMode.FIXED,
            ),
        ),
        initial_state="ACTIVE",
        lifecycle_states=(
            LifecycleStateDefinition("ACTIVE", initial=True),
            LifecycleStateDefinition("OUT_OF_SERVICE"),
        ),
        lifecycle_transitions=(
            LifecycleTransitionDefinition(
                "ACTIVE",
                "OUT_OF_SERVICE",
                allowed_roles=("QMB",),
                reason_required=True,
            ),
        ),
    )
    return ModuleBlueprintDraft(
        key=key,
        name="Gerätemanagement",
        description="Geräte, Wartungen und Nachweise",
        root_template_key="device",
        templates=(device, evidence, maintenance),
    )


def test_validate_publish_list_and_instantiate_blueprint_atomically(setup, admin):
    api, events = setup
    validation = api.validate_module_blueprint(admin, device_blueprint())
    assert validation.valid
    assert validation.deployment_order.index("maintenance") < validation.deployment_order.index("device")

    published = api.publish_module_blueprint(admin, device_blueprint())
    assert published.blueprint_key == "device-management"
    assert published.root_template_version_uid
    assert len(published.templates) == 3
    assert all(
        api.get_template_version(admin, template.template_version_uid).state is TemplateState.PUBLISHED
        for template in published.templates
    )
    assert [item.uid for item in api.list_module_blueprints(admin)] == [published.uid]

    device = api.create_object(
        admin,
        published.root_template_version_uid,
        StructuralParentRef(ParentKind.WORKSPACE_ROOT, api.workspace_root_uid()),
        values={"serial_number": "DEV-001"},
    )
    children = api.list_children(admin, StructuralParentRef(ParentKind.OBJECT, device.uid))
    assert len(children) == 1 and children[0].fixed
    assert any(event.name == "domain.container.module_blueprint.published.v1" for event in events.events)


def test_blueprint_validation_rejects_cycle_missing_target_and_duplicate_publish(setup, admin):
    api, _ = setup
    cycle = ModuleBlueprintDraft(
        key="cyclic-module",
        name="Zyklus",
        description="",
        root_template_key="one",
        templates=(
            BlueprintTemplateDraft(
                "one",
                TemplateKind.OBJECT,
                "Eins",
                ("ADMIN",),
                children=(BlueprintChildDefinition("two", "two"),),
            ),
            BlueprintTemplateDraft(
                "two",
                TemplateKind.OBJECT,
                "Zwei",
                ("ADMIN",),
                children=(BlueprintChildDefinition("one", "one"),),
            ),
        ),
    )
    validation = api.validate_module_blueprint(admin, cycle)
    assert not validation.valid
    assert "container.blueprint.cycle" in {issue.code for issue in validation.issues}

    missing = device_blueprint()
    broken_device = BlueprintTemplateDraft(
        key="device",
        kind=TemplateKind.OBJECT,
        name="Gerät",
        create_roles=("ADMIN",),
        children=(BlueprintChildDefinition("missing", "does-not-exist"),),
    )
    missing = ModuleBlueprintDraft(
        missing.key,
        missing.name,
        missing.description,
        missing.root_template_key,
        (broken_device,),
    )
    validation = api.validate_module_blueprint(admin, missing)
    assert "container.blueprint.child_template_not_found" in {issue.code for issue in validation.issues}

    required_auto_child = ModuleBlueprintDraft(
        key="required-auto-child",
        name="Ungültige Autoanlage",
        description="",
        root_template_key="parent",
        templates=(
            BlueprintTemplateDraft(
                "parent",
                TemplateKind.OBJECT,
                "Parent",
                ("ADMIN",),
                children=(BlueprintChildDefinition("child", "child", min_count=1, auto_create=True),),
            ),
            BlueprintTemplateDraft(
                "child",
                TemplateKind.OBJECT,
                "Child",
                ("ADMIN",),
                fields=(FieldDefinition("required_value", FieldType.STRING, required=True),),
            ),
        ),
    )
    validation = api.validate_module_blueprint(admin, required_auto_child)
    assert "container.blueprint.auto_child_required_fields" in {issue.code for issue in validation.issues}

    api.publish_module_blueprint(admin, device_blueprint())
    duplicate = api.validate_module_blueprint(admin, device_blueprint())
    assert not duplicate.valid
    assert "container.blueprint.key_exists" in {issue.code for issue in duplicate.issues}
    with pytest.raises(ContainerError) as error:
        api.publish_module_blueprint(admin, device_blueprint())
    assert error.value.code == "container.blueprint.invalid"
    assert len(api.list_module_blueprints(admin)) == 1


def test_blueprint_commands_require_confirmed_admin(setup, admin):
    api, _ = setup
    viewer = issue_user_context(
        user_id="viewer",
        session_id="viewer",
        request_id="viewer",
        username="viewer",
        global_roles={"USER"},
        is_qmb=False,
        authenticated_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ContainerError) as error:
        api.validate_module_blueprint(viewer, device_blueprint())
    assert error.value.code == "container.authorization.template_denied"
    with pytest.raises(ContainerError) as error:
        api.publish_module_blueprint(object(), device_blueprint())
    assert error.value.code == "container.authorization.confirmed_actor_required"
