"""Container HTTP transport.  Commands are deliberately thin adapters to ``ContainerApi``."""
from __future__ import annotations

import base64
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from modules.container import api as container_api
from modules.usermanagement.api import UserContext
from src.backend.auth_dependencies import require_user_context_normal

router = APIRouter(prefix="/container", tags=["container"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(StrictModel):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)
    hint_code: str | None = None


class FieldDefinitionCommand(StrictModel):
    key: str = Field(min_length=1)
    field_type: container_api.FieldType
    required: bool = False
    searchable: bool = False
    linkable: bool = False
    printable: bool = False
    relevant_for_review: bool = False
    historized: bool = False
    editable: bool = True
    visible: bool = True
    options: list[str] = Field(default_factory=list)


class ChildDefinitionCommand(StrictModel):
    key: str = Field(min_length=1)
    template_version_uid: str = Field(min_length=1)
    min_count: int = Field(default=0, ge=0)
    max_count: int | None = Field(default=None, ge=0)
    auto_create: bool = False
    mode: container_api.ChildMode = container_api.ChildMode.FLEXIBLE


class BlueprintChildCommand(StrictModel):
    key: str = Field(min_length=1)
    template_key: str = Field(min_length=1)
    min_count: int = Field(default=0, ge=0)
    max_count: int | None = Field(default=None, ge=0)
    auto_create: bool = False
    mode: container_api.ChildMode = container_api.ChildMode.FLEXIBLE


class LifecycleStateCommand(StrictModel):
    code: str = Field(min_length=1)
    initial: bool = False


class LifecycleTransitionCommand(StrictModel):
    from_state: str = Field(min_length=1)
    to_state: str = Field(min_length=1)
    allowed_roles: list[str] = Field(default_factory=list)
    reason_required: bool = False
    signature_required: bool = False


class TemplateCommand(StrictModel):
    kind: container_api.TemplateKind
    name: str = Field(min_length=1)
    version_number: int = Field(ge=1)
    create_roles: list[str]
    fields: list[FieldDefinitionCommand] = Field(default_factory=list)
    children: list[ChildDefinitionCommand] = Field(default_factory=list)
    initial_state: str = "ACTIVE"
    lifecycle_states: list[LifecycleStateCommand] = Field(default_factory=list)
    lifecycle_transitions: list[LifecycleTransitionCommand] = Field(default_factory=list)
    template_uid: str | None = None


class BlueprintTemplateCommand(StrictModel):
    key: str = Field(min_length=1, max_length=64)
    kind: container_api.TemplateKind
    name: str = Field(min_length=1, max_length=120)
    create_roles: list[str] = Field(min_length=1)
    fields: list[FieldDefinitionCommand] = Field(default_factory=list)
    children: list[BlueprintChildCommand] = Field(default_factory=list)
    initial_state: str = Field(default="ACTIVE", min_length=1)
    lifecycle_states: list[LifecycleStateCommand] = Field(default_factory=list)
    lifecycle_transitions: list[LifecycleTransitionCommand] = Field(default_factory=list)


class ModuleBlueprintCommand(StrictModel):
    key: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    root_template_key: str = Field(min_length=1, max_length=64)
    templates: list[BlueprintTemplateCommand] = Field(min_length=1, max_length=50)


class ObjectCreateCommand(StrictModel):
    template_version_uid: str
    parent_kind: container_api.ParentKind
    parent_uid: str
    values: dict[str, Any] = Field(default_factory=dict)


class ValuesCommand(StrictModel):
    values: dict[str, Any]
    expected_revision: int = Field(ge=1)


class MoveCommand(StrictModel):
    parent_kind: container_api.ParentKind
    parent_uid: str
    expected_revision: int = Field(ge=1)


class ArtifactCreateCommand(StrictModel):
    template_version_uid: str
    owner_object_uid: str
    values: dict[str, Any] = Field(default_factory=dict)


class UploadCommand(StrictModel):
    original_name: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=255)
    content_base64: str
    expected_revision: int = Field(ge=1)


class RevisionCommand(StrictModel):
    expected_revision: int = Field(ge=1)


class MeaningCommand(StrictModel):
    meaning: str = Field(min_length=1, max_length=500)


class TransitionCommand(RevisionCommand):
    to_state: str
    reason: str | None = None
    signature_meaning: str | None = None

class ReferenceCommand(StrictModel):
    source_kind: container_api.ReferenceKind; source_uid: str; target_kind: container_api.ReferenceKind; target_uid: str; link_type_uid: str
class ExternalCommand(StrictModel):
    source_kind: container_api.ReferenceKind; source_uid: str; provider_code: str; module_code: str; entity_uid: str; mode: container_api.ExternalReferenceMode; fixed_version_uid: str | None = None
class MigrationCommand(RevisionCommand):
    target_published_version_uid: str; values_for_new_required: dict[str, Any] = Field(default_factory=dict)
class StoreExportCommand(StrictModel):
    artifact_template_version_uid: str; include_artifacts: bool = True; include_files: bool = True; printable: bool = False; values: dict[str, Any] = Field(default_factory=dict)
class DeletionPolicyCommand(StrictModel):
    allowed_role_codes: list[str]; require_backup: bool; require_second_approver: bool; template_version_uid: str | None = None
class BackupCommand(StrictModel):
    scope_uid: str; integrity_hash: str
class ApprovalCommand(StrictModel):
    requester_user_id: str
class DeleteCommand(StrictModel):
    reason: str; backup_evidence_uid: str | None = None; approval_uid: str | None = None


def _api(request: Request):
    container = getattr(request.app.state, "container", None)
    if container is None or not container.has_port("container_api"):
        raise HTTPException(status_code=503, detail=ErrorResponse(code="container.unavailable").model_dump())
    return container.get_port("container_api")


def _json(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, (date, datetime)): return value.isoformat()
    if is_dataclass(value): return {key: _json(item) for key, item in asdict(value).items()}
    if isinstance(value, dict): return {str(key.value if isinstance(key, Enum) else key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_json(item) for item in value]
    return value


def _call(fn):
    try:
        return _json(fn())
    except container_api.ContainerError as exc:
        code = exc.code
        if ".not_found" in code or code.endswith((".not_found", "_not_found")): status = 404
        elif "authorization" in code or ".denied" in code or "read_only" in code: status = 403
        elif "conflict" in code or "immutable" in code or "already_" in code or code.endswith("_exists"): status = 409
        elif "unavailable" in code: status = 503
        else: status = 422
        raise HTTPException(status_code=status, detail=ErrorResponse(code=code, params=exc.params).model_dump()) from exc


def _draft(body: TemplateCommand) -> container_api.TemplateDraft:
    fields = tuple(
        container_api.FieldDefinition(
            **item.model_dump(exclude={"options"}), options=tuple(item.options)
        )
        for item in body.fields
    )
    children = tuple(container_api.ChildDefinition(**item.model_dump()) for item in body.children)
    return container_api.TemplateDraft(
        kind=body.kind, name=body.name, version_number=body.version_number, create_roles=tuple(body.create_roles),
        fields=fields, children=children, initial_state=body.initial_state,
        lifecycle_states=tuple(container_api.LifecycleStateDefinition(**item.model_dump()) for item in body.lifecycle_states),
        lifecycle_transitions=tuple(
            container_api.LifecycleTransitionDefinition(
                **item.model_dump(exclude={"allowed_roles"}),
                allowed_roles=tuple(item.allowed_roles),
            )
            for item in body.lifecycle_transitions
        ),
        template_uid=body.template_uid,
    )


def _blueprint(body: ModuleBlueprintCommand) -> container_api.ModuleBlueprintDraft:
    templates = []
    for template in body.templates:
        fields = tuple(
            container_api.FieldDefinition(
                **item.model_dump(exclude={"options"}),
                options=tuple(item.options),
            )
            for item in template.fields
        )
        children = tuple(
            container_api.BlueprintChildDefinition(**item.model_dump())
            for item in template.children
        )
        states = tuple(
            container_api.LifecycleStateDefinition(**item.model_dump())
            for item in template.lifecycle_states
        )
        transitions = tuple(
            container_api.LifecycleTransitionDefinition(
                **item.model_dump(exclude={"allowed_roles"}),
                allowed_roles=tuple(item.allowed_roles),
            )
            for item in template.lifecycle_transitions
        )
        templates.append(
            container_api.BlueprintTemplateDraft(
                key=template.key,
                kind=template.kind,
                name=template.name,
                create_roles=tuple(template.create_roles),
                fields=fields,
                children=children,
                initial_state=template.initial_state,
                lifecycle_states=states,
                lifecycle_transitions=transitions,
            )
        )
    return container_api.ModuleBlueprintDraft(
        key=body.key,
        name=body.name,
        description=body.description,
        root_template_key=body.root_template_key,
        templates=tuple(templates),
    )


@router.get("/status")
def status(request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    api = _api(request)
    return {"status": "ok", "workspace_root_uid": api.workspace_root_uid(), "capabilities": ["container.object.manage", "container.artifact.manage", "container.reference.manage", "container.export.manage", "container.blueprint.manage"]}


@router.get("/workspace-root")
def workspace_root(request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return {"uid": _api(request).workspace_root_uid()}


@router.get("/blueprints")
def module_blueprints(request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_module_blueprints(actor))


@router.post("/blueprints/validate")
def validate_blueprint(body: ModuleBlueprintCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).validate_module_blueprint(actor, _blueprint(body)))


@router.post("/blueprints/publish")
def publish_blueprint(body: ModuleBlueprintCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).publish_module_blueprint(actor, _blueprint(body)))


@router.post("/templates/drafts")
def create_draft(body: TemplateCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).create_template_draft(actor, _draft(body)))


@router.post("/templates/{template_version_uid}/publish")
def publish_template(template_version_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).publish_template(actor, template_version_uid))


@router.get("/templates/{template_version_uid}")
def template(template_version_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).get_template_version(actor, template_version_uid))


@router.post("/objects")
def create_object(body: ObjectCreateCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).create_object(actor, body.template_version_uid, container_api.StructuralParentRef(body.parent_kind, body.parent_uid), values=body.values))


@router.get("/objects/search")
def search(
    query: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_user_context_normal)],
    field_keys: list[str] | None = None,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    return _call(
        lambda: _api(request).search_objects(
            actor,
            query,
            field_keys=tuple(field_keys) if field_keys else None,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/objects/{object_uid}")
def object_detail(object_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).get_object_detail(actor, object_uid))


@router.put("/objects/{object_uid}/fields")
def update_object(object_uid: str, body: ValuesCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).update_object_fields(actor, object_uid, body.values, expected_revision=body.expected_revision))


@router.post("/objects/{object_uid}/move")
def move_object(object_uid: str, body: MoveCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).move_object(actor, object_uid, container_api.StructuralParentRef(body.parent_kind, body.parent_uid), expected_revision=body.expected_revision))


@router.get("/objects/{object_uid}/children")
def children(object_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_children(actor, container_api.StructuralParentRef(container_api.ParentKind.OBJECT, object_uid)))


@router.post("/objects/{object_uid}/transition")
def transition_object(object_uid: str, body: TransitionCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).transition_object(actor, object_uid, to_state=body.to_state, reason=body.reason, signature_meaning=body.signature_meaning, expected_revision=body.expected_revision))


@router.post("/objects/{object_uid}/archive")
def archive_object(object_uid: str, body: RevisionCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).archive_object(actor, object_uid, expected_revision=body.expected_revision))


@router.post("/objects/{object_uid}/reactivate")
def reactivate_object(object_uid: str, body: RevisionCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).reactivate_object(actor, object_uid, expected_revision=body.expected_revision))


@router.post("/objects/{object_uid}/sign")
def sign_object(object_uid: str, body: MeaningCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).sign_object(actor, object_uid, meaning=body.meaning))


@router.get("/objects/{object_uid}/signatures")
def object_signatures(object_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_object_signatures(actor, object_uid))


@router.get("/objects/{object_uid}/audit")
def object_audit(object_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_audit_records(actor, kind=container_api.ReferenceKind.OBJECT, uid=object_uid))

@router.post("/objects/{object_uid}/template-migrate")
def migrate_template(object_uid: str, body: MigrationCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).migrate_object_template(actor, object_uid, body.target_published_version_uid, expected_revision=body.expected_revision, values_for_new_required=body.values_for_new_required))


@router.post("/artifacts")
def create_artifact(body: ArtifactCreateCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).create_artifact(actor, body.template_version_uid, body.owner_object_uid, values=body.values))


@router.get("/artifacts/{artifact_uid}")
def artifact_detail(artifact_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).get_artifact_detail(actor, artifact_uid))


@router.put("/artifacts/{artifact_uid}/fields")
def update_artifact(artifact_uid: str, body: ValuesCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).update_artifact_fields(actor, artifact_uid, body.values, expected_revision=body.expected_revision))


@router.post("/artifacts/{artifact_uid}/files")
def upload_file(artifact_uid: str, body: UploadCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=ErrorResponse(code="container.storage.invalid_base64").model_dump()) from exc
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail=ErrorResponse(code="container.storage.file_too_large", params={"max_bytes": MAX_UPLOAD_BYTES}).model_dump())
    return _call(lambda: _api(request).add_artifact_file(actor, artifact_uid, content, original_name=body.original_name, media_type=body.media_type, expected_revision=body.expected_revision))


@router.get("/artifacts/{artifact_uid}/files/{file_uid}/download")
def download_file(artifact_uid: str, file_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    def content():
        file = _api(request).get_artifact_file(actor, file_uid)
        return file, _api(request).read_artifact_file(actor, artifact_uid, file_uid)
    file, data = _call(content)
    encoded_name = quote(file["original_name"], safe="")
    disposition = f"attachment; filename=download; filename*=UTF-8''{encoded_name}"
    return Response(data, media_type=file["media_type"], headers={"Content-Disposition": disposition})


@router.post("/artifacts/{artifact_uid}/finalize")
def finalize(artifact_uid: str, body: RevisionCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).finalize_artifact(actor, artifact_uid, expected_revision=body.expected_revision))


@router.post("/artifacts/{artifact_uid}/sign")
def sign_artifact(artifact_uid: str, body: MeaningCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).sign_artifact(actor, artifact_uid, meaning=body.meaning))


@router.post("/artifacts/{artifact_uid}/correct")
def correct_artifact(artifact_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).correct_artifact(actor, artifact_uid))


@router.get("/objects/{object_uid}/export")
def export_object(object_uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    try:
        bundle = _api(request).export_object_subtree(actor, object_uid, include_files=True)
    except container_api.ContainerError as exc:
        return _call(lambda: (_ for _ in ()).throw(exc))
    filename = f"container-export-{object_uid}.zip"
    return Response(bundle.zip_bytes, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Container-Export-UID": bundle.record.uid})

@router.post("/objects/{object_uid}/export/store-as-artifact")
def store_export(object_uid: str, body: StoreExportCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).store_export_as_artifact(actor, object_uid, body.artifact_template_version_uid, include_artifacts=body.include_artifacts, include_files=body.include_files, printable=body.printable, values=body.values))

@router.post("/references")
def create_reference(body: ReferenceCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).create_reference(actor, source_kind=body.source_kind, source_uid=body.source_uid, target_kind=body.target_kind, target_uid=body.target_uid, link_type_uid=body.link_type_uid))

@router.get("/references/{kind}/{uid}")
def references(kind: container_api.ReferenceKind, uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_references(actor, kind=kind, uid=uid))

@router.post("/external-references")
def create_external(body: ExternalCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).create_external_reference(actor, source_kind=body.source_kind, source_uid=body.source_uid, provider_code=body.provider_code, module_code=body.module_code, entity_uid=body.entity_uid, mode=body.mode, fixed_version_uid=body.fixed_version_uid))

@router.post("/external-references/{uid}/resolve")
def resolve_external(uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: {"resolved_version_uid": _api(request).resolve_external_reference(actor, uid)})

@router.get("/external-references/{uid}/resolutions")
def external_resolutions(uid: str, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_external_reference_resolutions(actor, uid))

@router.post("/deletion-policy")
def deletion_policy(body: DeletionPolicyCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).configure_deletion_policy(actor, allowed_role_codes=tuple(body.allowed_role_codes), require_backup=body.require_backup, require_second_approver=body.require_second_approver, template_version_uid=body.template_version_uid))

@router.post("/backups")
def backup(body: BackupCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).create_backup_evidence(actor, scope_uid=body.scope_uid, integrity_hash=body.integrity_hash))

@router.post("/objects/{object_uid}/deletion-approvals")
def approval(object_uid: str, body: ApprovalCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).approve_physical_deletion(actor, object_uid=object_uid, requester_user_id=body.requester_user_id))

@router.post("/objects/{object_uid}/physical-delete")
def physical_delete(object_uid: str, body: DeleteCommand, request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).physical_delete_object(actor, object_uid, reason=body.reason, backup_evidence_uid=body.backup_evidence_uid, approval_uid=body.approval_uid))

@router.get("/tombstones")
def tombstones(request: Request, actor: Annotated[UserContext, Depends(require_user_context_normal)]):
    return _call(lambda: _api(request).list_tombstones(actor))
