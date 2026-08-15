from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TemplateKind(StrEnum):
    OBJECT = "OBJECT"
    ARTIFACT = "ARTIFACT"


class TemplateState(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DISABLED = "DISABLED"


class FieldType(StrEnum):
    STRING = "string"
    MULTILINE_TEXT = "multiline_text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    USER_REFERENCE = "user_reference"
    OBJECT_REFERENCE = "object_reference"
    ARTIFACT_REFERENCE = "artifact_reference"


class ParentKind(StrEnum):
    WORKSPACE_ROOT = "WORKSPACE_ROOT"
    OBJECT = "OBJECT"


class ChildMode(StrEnum):
    FIXED = "FIXED"
    MAINTENANCE = "MAINTENANCE"
    FLEXIBLE = "FLEXIBLE"


class ActionCode(StrEnum):
    VIEW = "VIEW"
    SEARCH = "SEARCH"
    UPDATE = "UPDATE"
    MOVE = "MOVE"
    CREATE_CHILD = "CREATE_CHILD"
    CREATE_ARTIFACT = "CREATE_ARTIFACT"
    TRANSITION = "TRANSITION"
    ARCHIVE = "ARCHIVE"
    REACTIVATE = "REACTIVATE"
    REFERENCE = "REFERENCE"
    FINALIZE = "FINALIZE"
    SIGN = "SIGN"
    CORRECT = "CORRECT"
    PHYSICAL_DELETE = "PHYSICAL_DELETE"


class DeletionPolicyScope(StrEnum):
    GLOBAL = "GLOBAL"
    TEMPLATE = "TEMPLATE"


class ReferenceKind(StrEnum):
    OBJECT = "OBJECT"
    ARTIFACT = "ARTIFACT"


class ExternalReferenceMode(StrEnum):
    FIXED = "FIXED"
    DYNAMIC = "DYNAMIC"


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    denial_code: str | None = None
    params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LinkType:
    uid: str
    code: str
    source_kind: ReferenceKind
    target_kind: ReferenceKind
    inverse_label: str | None = None


@dataclass(frozen=True)
class ContainerReference:
    uid: str
    source_kind: ReferenceKind
    source_uid: str
    target_kind: ReferenceKind
    target_uid: str
    link_type_uid: str


@dataclass(frozen=True)
class ObjectSnapshot:
    uid: str
    object_uid: str
    state_hash: str
    revision: int


@dataclass(frozen=True)
class ObjectSignature:
    uid: str
    object_uid: str
    snapshot_uid: str
    state_hash: str
    signer_user_id: str
    meaning: str


@dataclass(frozen=True)
class ExternalReferenceTarget:
    uid: str
    source_kind: ReferenceKind
    source_uid: str
    provider_code: str
    module_code: str
    entity_uid: str
    mode: ExternalReferenceMode
    fixed_version_uid: str | None


@dataclass(frozen=True)
class ExternalReferenceResolution:
    uid: str
    external_reference_target_uid: str
    resolved_version_uid: str
    resolved_by: str


@dataclass(frozen=True)
class AuditRecord:
    uid: str
    event_type: str
    aggregate_uid: str
    actor_user_id: str
    occurred_at: str | None = None
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LifecycleStateDefinition:
    code: str
    initial: bool = False


@dataclass(frozen=True)
class LifecycleTransitionDefinition:
    from_state: str
    to_state: str
    allowed_roles: tuple[str, ...] = ()
    reason_required: bool = False
    signature_required: bool = False


@dataclass(frozen=True)
class FieldDefinition:
    key: str
    field_type: FieldType
    required: bool = False
    searchable: bool = False
    linkable: bool = False
    printable: bool = False
    relevant_for_review: bool = False
    historized: bool = False
    editable: bool = True
    visible: bool = True
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChildDefinition:
    key: str
    template_version_uid: str
    min_count: int = 0
    max_count: int | None = None
    auto_create: bool = False
    mode: ChildMode = ChildMode.FLEXIBLE


@dataclass(frozen=True)
class BlueprintChildDefinition:
    key: str
    template_key: str
    min_count: int = 0
    max_count: int | None = None
    auto_create: bool = False
    mode: ChildMode = ChildMode.FLEXIBLE


@dataclass(frozen=True)
class BlueprintTemplateDraft:
    key: str
    kind: TemplateKind
    name: str
    create_roles: tuple[str, ...]
    fields: tuple[FieldDefinition, ...] = ()
    children: tuple[BlueprintChildDefinition, ...] = ()
    initial_state: str = "ACTIVE"
    lifecycle_states: tuple[LifecycleStateDefinition, ...] = ()
    lifecycle_transitions: tuple[LifecycleTransitionDefinition, ...] = ()


@dataclass(frozen=True)
class ModuleBlueprintDraft:
    key: str
    name: str
    description: str
    root_template_key: str
    templates: tuple[BlueprintTemplateDraft, ...]


@dataclass(frozen=True)
class BlueprintIssue:
    code: str
    template_key: str | None = None
    params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BlueprintValidation:
    valid: bool
    deployment_order: tuple[str, ...]
    issues: tuple[BlueprintIssue, ...]


@dataclass(frozen=True)
class PublishedBlueprintTemplate:
    template_key: str
    template_version_uid: str
    kind: TemplateKind
    name: str
    is_root: bool = False


@dataclass(frozen=True)
class PublishedModuleBlueprint:
    uid: str
    blueprint_key: str
    name: str
    description: str
    root_template_version_uid: str
    templates: tuple[PublishedBlueprintTemplate, ...]
    published_by: str


@dataclass(frozen=True)
class TemplateDraft:
    kind: TemplateKind
    name: str
    version_number: int
    create_roles: tuple[str, ...]
    fields: tuple[FieldDefinition, ...] = ()
    children: tuple[ChildDefinition, ...] = ()
    initial_state: str = "ACTIVE"
    lifecycle_states: tuple[LifecycleStateDefinition, ...] = ()
    lifecycle_transitions: tuple[LifecycleTransitionDefinition, ...] = ()
    template_uid: str | None = None


@dataclass(frozen=True)
class TemplateVersion:
    uid: str
    template_uid: str
    kind: TemplateKind
    name: str
    version_number: int
    state: TemplateState
    create_roles: tuple[str, ...]
    initial_state: str


@dataclass(frozen=True)
class StructuralParentRef:
    kind: ParentKind
    uid: str


@dataclass(frozen=True)
class ContainerObject:
    uid: str
    template_version_uid: str
    parent: StructuralParentRef
    depth: int
    revision: int
    state: str
    fixed: bool
    archived: bool = False


@dataclass(frozen=True)
class Artifact:
    uid: str
    template_version_uid: str
    owner_object_uid: str
    state: str
    revision: int
    immutable: bool
    final_snapshot_uid: str | None
    archived: bool = False


@dataclass(frozen=True)
class ObjectDetail:
    entity: ContainerObject
    field_values: dict[str, object]
    allowed_actions: dict[ActionCode, ActionDecision]
    references: tuple[ContainerReference, ...]


@dataclass(frozen=True)
class ArtifactDetail:
    entity: Artifact
    field_values: dict[str, object]
    allowed_actions: dict[ActionCode, ActionDecision]
    references: tuple[ContainerReference, ...]
    files: tuple["ArtifactFile", ...] = ()


@dataclass(frozen=True)
class ArtifactFile:
    uid: str
    artifact_uid: str
    original_name: str
    media_type: str
    size_bytes: int
    content_hash: str
    immutable: bool


@dataclass(frozen=True)
class ArtifactSnapshot:
    uid: str
    artifact_uid: str
    state_hash: str
    template_version_uid: str


@dataclass(frozen=True)
class ArtifactSignature:
    uid: str
    artifact_uid: str
    snapshot_uid: str
    state_hash: str
    signer_user_id: str
    meaning: str


@dataclass(frozen=True)
class AuditEvent:
    uid: str
    event_type: str
    aggregate_uid: str
    actor_user_id: str


@dataclass(frozen=True)
class DeletionPolicy:
    uid: str
    scope: DeletionPolicyScope
    template_version_uid: str | None
    allowed_role_codes: tuple[str, ...]
    require_backup: bool
    require_second_approver: bool


@dataclass(frozen=True)
class BackupEvidence:
    uid: str
    scope_uid: str
    integrity_hash: str
    created_by: str


@dataclass(frozen=True)
class PhysicalDeletionApproval:
    uid: str
    object_uid: str
    requester_user_id: str
    approved_by: str


@dataclass(frozen=True)
class Tombstone:
    uid: str
    deleted_entity_uid: str
    deleted_entity_kind: str
    backup_evidence_uid: str | None
    deletion_approval_uid: str | None
    deleted_by: str
    reason: str


@dataclass(frozen=True)
class TemplateMigrationRecord:
    uid: str
    object_uid: str
    old_template_version_uid: str
    new_template_version_uid: str
    migrated_by: str


@dataclass(frozen=True)
class ExportRecord:
    uid: str
    root_object_uid: str
    manifest_hash: str
    created_by: str
    include_artifacts: bool
    include_files: bool
    printable: bool


@dataclass(frozen=True)
class ExportBundle:
    record: ExportRecord
    manifest: dict[str, object]
    zip_bytes: bytes
    printable_text: str | None
    stored_artifact_uid: str | None = None
