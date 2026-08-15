from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from modules.usermanagement.api import require_confirmed_user_context
from qm_platform.events.event_envelope import EventEnvelope

from .domain import (
    ActionCode, ActionDecision, Artifact, ArtifactDetail, ArtifactFile,
    ArtifactSignature, ArtifactSnapshot, AuditEvent, AuditRecord, BackupEvidence,
    BlueprintIssue, BlueprintTemplateDraft, BlueprintValidation, ChildDefinition,
    ChildMode, ContainerObject, ContainerReference, DeletionPolicy,
    DeletionPolicyScope, ExportBundle, ExportRecord, ExternalReferenceMode,
    ExternalReferenceResolution, ExternalReferenceTarget, FieldDefinition,
    FieldType, LifecycleStateDefinition, LinkType, ModuleBlueprintDraft,
    ObjectDetail, ObjectSignature, ObjectSnapshot, ParentKind,
    PhysicalDeletionApproval, PublishedBlueprintTemplate,
    PublishedModuleBlueprint, ReferenceKind, RuntimeModuleDefinition,
    RuntimeTemplateDefinition, RuntimeTransitionDefinition, StructuralParentRef,
    TemplateDraft, TemplateKind, TemplateMigrationRecord, TemplateState,
    TemplateVersion, Tombstone,
)
from .errors import ContainerError
from .sqlite_repository import SQLiteContainerRepository
from .storage import ArtifactFileStorage


MAX_OBJECT_DEPTH = 32


class ExternalReferenceResolver(Protocol):
    def resolve(self, *, provider_code: str, module_code: str, entity_uid: str) -> str: ...


class ContainerService:
    def __init__(self, repository: SQLiteContainerRepository, *, event_bus, artifact_storage: ArtifactFileStorage | None = None, external_reference_resolver: ExternalReferenceResolver | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._artifact_storage = artifact_storage
        self._external_reference_resolver = external_reference_resolver

    def create_template_draft(self, actor: object, draft: TemplateDraft) -> TemplateVersion:
        context = self._actor(actor)
        self._require_template_admin(context)
        self._validate_draft(draft)
        template_uid = draft.template_uid or self._uid()
        version_uid = self._uid()
        with self._repository.transaction() as conn:
            self._insert_template_header(conn, context.user_id, draft, template_uid, version_uid)
            self._insert_template_components(conn, draft, version_uid)
            self._audit(conn, "template.draft.created", version_uid, context.user_id)
        return self._get_template_version(version_uid)

    def publish_template(self, actor: object, template_version_uid: str) -> TemplateVersion:
        context = self._actor(actor)
        self._require_template_admin(context)
        with self._repository.transaction() as conn:
            version = conn.execute("SELECT * FROM template_versions WHERE uid=?", (template_version_uid,)).fetchone()
            if version is None:
                raise ContainerError("container.template.not_found", template_version_uid=template_version_uid)
            if version["state"] != TemplateState.DRAFT.value:
                raise ContainerError("container.template.not_draft", template_version_uid=template_version_uid)
            self._assert_publishable(conn, template_version_uid)
            conn.execute("UPDATE template_versions SET state=?, published_at=CURRENT_TIMESTAMP WHERE uid=?", (TemplateState.PUBLISHED.value, template_version_uid))
            self._audit(conn, "template.published", template_version_uid, context.user_id)
        self._publish("domain.container.template.published.v1", template_version_uid, context)
        return self._get_template_version(template_version_uid)

    def get_template_version(self, actor: object, template_version_uid: str) -> TemplateVersion:
        context = self._actor(actor)
        self._require_template_admin(context)
        return self._get_template_version(template_version_uid)

    def validate_module_blueprint(self, actor: object, draft: ModuleBlueprintDraft) -> BlueprintValidation:
        context = self._actor(actor)
        self._require_template_admin(context)
        issues: list[BlueprintIssue] = []
        blueprint_key_valid = isinstance(draft.key, str) and bool(re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", draft.key))
        if not blueprint_key_valid:
            issues.append(BlueprintIssue("container.blueprint.invalid_key"))
        if not isinstance(draft.name, str) or not draft.name.strip() or len(draft.name.strip()) > 120:
            issues.append(BlueprintIssue("container.blueprint.invalid_name"))
        if not isinstance(draft.description, str) or len(draft.description) > 1000:
            issues.append(BlueprintIssue("container.blueprint.description_too_long"))
        if not draft.templates or len(draft.templates) > 50:
            issues.append(BlueprintIssue("container.blueprint.invalid_template_count"))

        keys = [template.key for template in draft.templates]
        if len(keys) != len(set(keys)):
            issues.append(BlueprintIssue("container.blueprint.duplicate_template_key"))
        templates = {template.key: template for template in draft.templates}
        for template in draft.templates:
            if not isinstance(template.key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", template.key):
                issues.append(BlueprintIssue("container.blueprint.invalid_template_key", template.key))
            converted = self._blueprint_template_draft(template, {})
            try:
                self._validate_draft(converted)
            except ContainerError as exc:
                issues.append(BlueprintIssue(exc.code, template.key, dict(exc.params)))
            for child in template.children:
                target = templates.get(child.template_key)
                if target is None:
                    issues.append(BlueprintIssue(
                        "container.blueprint.child_template_not_found",
                        template.key,
                        {"child_key": child.key, "template_key": child.template_key},
                    ))
                elif target.kind is not TemplateKind.OBJECT:
                    issues.append(BlueprintIssue(
                        "container.blueprint.child_must_be_object",
                        template.key,
                        {"child_key": child.key, "template_key": child.template_key},
                    ))
                elif (child.auto_create or child.min_count > 0) and any(field.required for field in target.fields):
                    issues.append(BlueprintIssue(
                        "container.blueprint.auto_child_required_fields",
                        template.key,
                        {"child_key": child.key, "template_key": child.template_key},
                    ))

        root = templates.get(draft.root_template_key)
        if root is None:
            issues.append(BlueprintIssue("container.blueprint.root_not_found"))
        elif root.kind is not TemplateKind.OBJECT:
            issues.append(BlueprintIssue("container.blueprint.root_must_be_object", root.key))

        deployment_order: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()
        cycle_reported = False

        def visit(template_key: str) -> None:
            nonlocal cycle_reported
            if template_key in visited:
                return
            if template_key in visiting:
                if not cycle_reported:
                    issues.append(BlueprintIssue("container.blueprint.cycle", template_key))
                    cycle_reported = True
                return
            visiting.add(template_key)
            template = templates.get(template_key)
            if template is not None:
                for child in template.children:
                    if child.template_key in templates:
                        visit(child.template_key)
            visiting.remove(template_key)
            visited.add(template_key)
            deployment_order.append(template_key)

        for template in draft.templates:
            visit(template.key)

        if blueprint_key_valid:
            with self._repository.read() as conn:
                if conn.execute("SELECT 1 FROM module_blueprints WHERE blueprint_key=?", (draft.key,)).fetchone():
                    issues.append(BlueprintIssue("container.blueprint.key_exists"))
        return BlueprintValidation(not issues, tuple(deployment_order), tuple(issues))

    def publish_module_blueprint(self, actor: object, draft: ModuleBlueprintDraft) -> PublishedModuleBlueprint:
        context = self._actor(actor)
        validation = self.validate_module_blueprint(context, draft)
        if not validation.valid:
            raise ContainerError(
                "container.blueprint.invalid",
                issues=[issue.code for issue in validation.issues],
            )
        identifiers = {
            template.key: (self._uid(), self._uid())
            for template in draft.templates
        }
        resolved_drafts = {
            template.key: self._blueprint_template_draft(
                template,
                {key: version_uid for key, (_, version_uid) in identifiers.items()},
            )
            for template in draft.templates
        }
        blueprint_uid = self._uid()
        with self._repository.transaction() as conn:
            if conn.execute("SELECT 1 FROM module_blueprints WHERE blueprint_key=?", (draft.key,)).fetchone():
                raise ContainerError("container.blueprint.key_exists", blueprint_key=draft.key)
            for template in draft.templates:
                template_uid, version_uid = identifiers[template.key]
                self._insert_template_header(
                    conn,
                    context.user_id,
                    resolved_drafts[template.key],
                    template_uid,
                    version_uid,
                )
            for template in draft.templates:
                _, version_uid = identifiers[template.key]
                self._insert_template_components(conn, resolved_drafts[template.key], version_uid)
                self._audit(conn, "template.draft.created", version_uid, context.user_id)
            for template_key in validation.deployment_order:
                _, version_uid = identifiers[template_key]
                self._assert_publishable(conn, version_uid)
                conn.execute(
                    "UPDATE template_versions SET state=?,published_at=CURRENT_TIMESTAMP WHERE uid=?",
                    (TemplateState.PUBLISHED.value, version_uid),
                )
                self._audit(conn, "template.published", version_uid, context.user_id)
            root_version_uid = identifiers[draft.root_template_key][1]
            conn.execute(
                "INSERT INTO module_blueprints(uid,blueprint_key,name,description,root_template_version_uid,published_by) VALUES(?,?,?,?,?,?)",
                (blueprint_uid, draft.key, draft.name.strip(), draft.description.strip(), root_version_uid, context.user_id),
            )
            for template in draft.templates:
                _, version_uid = identifiers[template.key]
                conn.execute(
                    "INSERT INTO module_blueprint_templates(module_blueprint_uid,template_key,template_version_uid,is_root) VALUES(?,?,?,?)",
                    (blueprint_uid, template.key, version_uid, int(template.key == draft.root_template_key)),
                )
            self._audit(
                conn,
                "module_blueprint.published",
                blueprint_uid,
                context.user_id,
                {"blueprint_key": draft.key, "root_template_version_uid": root_version_uid},
            )
        for template_key in validation.deployment_order:
            self._publish("domain.container.template.published.v1", identifiers[template_key][1], context)
        self._publish("domain.container.module_blueprint.published.v1", blueprint_uid, context)
        return self._get_module_blueprint(blueprint_uid)

    def list_module_blueprints(self, actor: object) -> list[PublishedModuleBlueprint]:
        context = self._actor(actor)
        self._require_template_admin(context)
        with self._repository.read() as conn:
            rows = conn.execute("SELECT uid FROM module_blueprints ORDER BY name,uid").fetchall()
        return [self._get_module_blueprint(row["uid"]) for row in rows]

    def list_runtime_modules(self, actor: object) -> list[RuntimeModuleDefinition]:
        """Return the permission-filtered module projection consumed by thin clients."""
        context = self._actor(actor)
        result: list[RuntimeModuleDefinition] = []
        with self._repository.read() as conn:
            workspace_root_uid = conn.execute("SELECT uid FROM workspace_roots WHERE singleton=1").fetchone()[0]
            blueprints = conn.execute("SELECT * FROM module_blueprints ORDER BY name,uid").fetchall()
            for blueprint in blueprints:
                template_rows = conn.execute(
                    """SELECT m.template_key,m.template_version_uid,m.is_root,v.kind,v.name
                       FROM module_blueprint_templates m
                       JOIN template_versions v ON v.uid=m.template_version_uid
                       WHERE m.module_blueprint_uid=? AND v.state=?
                       ORDER BY m.template_key""",
                    (blueprint["uid"], TemplateState.PUBLISHED.value),
                ).fetchall()
                templates = tuple(
                    self._runtime_template_definition(conn, context, row)
                    for row in template_rows
                )
                roots = conn.execute(
                    """SELECT * FROM objects
                       WHERE parent_kind=? AND parent_uid=? AND template_version_uid=?
                       ORDER BY created_at,uid""",
                    (
                        ParentKind.WORKSPACE_ROOT.value,
                        workspace_root_uid,
                        blueprint["root_template_version_uid"],
                    ),
                ).fetchall()
                visible_roots = tuple(
                    self._object_from_row(row)
                    for row in roots
                    if self._decision(
                        conn,
                        context,
                        ActionCode.VIEW,
                        ReferenceKind.OBJECT,
                        row["uid"],
                        row,
                    ).allowed
                )
                root_template = next((item for item in templates if item.is_root), None)
                if root_template is None or (not root_template.create_allowed and not visible_roots):
                    continue
                result.append(
                    RuntimeModuleDefinition(
                        uid=blueprint["uid"],
                        blueprint_key=blueprint["blueprint_key"],
                        name=blueprint["name"],
                        description=blueprint["description"],
                        root_template_version_uid=blueprint["root_template_version_uid"],
                        templates=templates,
                        root_objects=visible_roots,
                    )
                )
        return result

    def _get_template_version(self, template_version_uid: str) -> TemplateVersion:
        with self._repository.read() as conn:
            row = conn.execute("SELECT * FROM template_versions WHERE uid=?", (template_version_uid,)).fetchone()
            if row is None:
                raise ContainerError("container.template.not_found", template_version_uid=template_version_uid)
            roles = tuple(r[0] for r in conn.execute("SELECT role_code FROM template_create_roles WHERE template_version_uid=? ORDER BY role_code", (template_version_uid,)))
        return TemplateVersion(row["uid"], row["template_uid"], TemplateKind(row["kind"]), row["name"], row["version_number"], TemplateState(row["state"]), roles, row["initial_state"])

    def create_object(self, actor: object, template_version_uid: str, parent: StructuralParentRef, *, values: dict[str, object] | None = None) -> ContainerObject:
        context = self._actor(actor)
        values = values or {}
        events: list[tuple[str, str]] = []
        with self._repository.transaction() as conn:
            template = self._published_object_template(conn, template_version_uid)
            roles = {r[0] for r in conn.execute("SELECT role_code FROM template_create_roles WHERE template_version_uid=?", (template_version_uid,))}
            if not self._actor_allowed(context, roles):
                raise ContainerError("container.authorization.create_denied", template_version_uid=template_version_uid)
            if parent.kind is ParentKind.OBJECT:
                parent_row = self._aggregate_row(conn, ReferenceKind.OBJECT, parent.uid)
                if parent_row is None: raise ContainerError("container.tree.parent_not_found", parent_uid=parent.uid)
                self._require_action(conn, context, ActionCode.CREATE_CHILD, ReferenceKind.OBJECT, parent.uid, parent_row)
            parent_depth = self._parent_depth(conn, parent)
            if parent_depth + 1 > MAX_OBJECT_DEPTH:
                raise ContainerError("container.tree.max_depth", max_depth=MAX_OBJECT_DEPTH)
            result = self._insert_object(conn, context.user_id, template, parent, parent_depth + 1, values, fixed=False, events=events)
        for name, object_uid in events:
            self._publish(name, object_uid, context)
        return result

    def update_object_fields(self, actor: object, object_uid: str, values: dict[str, object], *, expected_revision: int) -> ContainerObject:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            obj = conn.execute("SELECT * FROM objects WHERE uid=?", (object_uid,)).fetchone()
            if obj is None:
                raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.UPDATE, ReferenceKind.OBJECT, object_uid, obj)
            if obj["revision"] != expected_revision:
                raise ContainerError("container.revision.conflict", expected=expected_revision, actual=obj["revision"])
            self._store_values(conn, obj["template_version_uid"], object_uid, values, replace=False, actor_id=context.user_id)
            conn.execute("UPDATE objects SET revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE uid=?", (object_uid,))
            self._audit(conn, "object.fields.updated", object_uid, context.user_id)
        return self.get_object(context, object_uid)

    def move_object(self, actor: object, object_uid: str, new_parent: StructuralParentRef, *, expected_revision: int) -> ContainerObject:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            obj = conn.execute("SELECT * FROM objects WHERE uid=?", (object_uid,)).fetchone()
            if obj is None:
                raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.MOVE, ReferenceKind.OBJECT, object_uid, obj)
            if obj["fixed"]:
                raise ContainerError("container.tree.fixed_child", object_uid=object_uid)
            if obj["revision"] != expected_revision:
                raise ContainerError("container.revision.conflict", expected=expected_revision, actual=obj["revision"])
            if new_parent.kind is ParentKind.OBJECT and new_parent.uid == object_uid:
                raise ContainerError("container.tree.cycle", object_uid=object_uid)
            if new_parent.kind is ParentKind.OBJECT and self._is_descendant(conn, new_parent.uid, object_uid):
                raise ContainerError("container.tree.cycle", object_uid=object_uid)
            if new_parent.kind is ParentKind.OBJECT:
                destination = self._aggregate_row(conn, ReferenceKind.OBJECT, new_parent.uid)
                if destination is None: raise ContainerError("container.tree.parent_not_found", parent_uid=new_parent.uid)
                self._require_action(conn, context, ActionCode.CREATE_CHILD, ReferenceKind.OBJECT, new_parent.uid, destination)
            parent_depth = self._parent_depth(conn, new_parent)
            subtree_height = self._subtree_height(conn, object_uid)
            if parent_depth + 1 + subtree_height > MAX_OBJECT_DEPTH:
                raise ContainerError("container.tree.max_depth", max_depth=MAX_OBJECT_DEPTH)
            self._assert_child_cardinality(conn, new_parent, obj["template_version_uid"], excluding_uid=object_uid)
            conn.execute("UPDATE objects SET parent_kind=?, parent_uid=?, depth=?, revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE uid=?", (new_parent.kind.value, new_parent.uid, parent_depth + 1, object_uid))
            delta = parent_depth + 1 - obj["depth"]
            self._shift_descendant_depths(conn, object_uid, delta)
            self._audit(conn, "object.moved", object_uid, context.user_id)
        self._publish("domain.container.object.moved.v1", object_uid, context)
        return self.get_object(context, object_uid)

    def get_object(self, actor: object, object_uid: str) -> ContainerObject:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = conn.execute("SELECT * FROM objects WHERE uid=?", (object_uid,)).fetchone()
            if row is not None:
                self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, object_uid, row)
        if row is None:
            raise ContainerError("container.object.not_found", object_uid=object_uid)
        return self._object_from_row(row)

    def get_object_detail(self, actor: object, object_uid: str) -> ObjectDetail:
        context = self._actor(actor)
        entity = self.get_object(context, object_uid)
        with self._repository.read() as conn:
            values = self._read_visible_values(conn, "object", object_uid)
            refs = tuple(self.list_references(context, kind=ReferenceKind.OBJECT, uid=object_uid))
            decisions = self.allowed_actions(context, ReferenceKind.OBJECT, object_uid)
            artifacts = tuple(
                self._artifact_from_row(row)
                for row in conn.execute(
                    "SELECT * FROM artifacts WHERE owner_object_uid=? ORDER BY created_at,uid",
                    (object_uid,),
                ).fetchall()
                if self._decision(
                    conn,
                    context,
                    ActionCode.VIEW,
                    ReferenceKind.ARTIFACT,
                    row["uid"],
                    row,
                ).allowed
            )
        return ObjectDetail(entity, values, decisions, refs, artifacts)

    def list_children(self, actor: object, parent: StructuralParentRef) -> list[ContainerObject]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            rows = conn.execute(
                "SELECT * FROM objects WHERE parent_kind=? AND parent_uid=? ORDER BY created_at, uid",
                (parent.kind.value, parent.uid),
            ).fetchall()
            rows = [row for row in rows if self._decision(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, row["uid"], row).allowed]
        return [self._object_from_row(row) for row in rows]

    def create_artifact(self, actor: object, template_version_uid: str, owner_object_uid: str, *, values: dict[str, object] | None = None) -> Artifact:
        context = self._actor(actor)
        values = values or {}
        with self._repository.transaction() as conn:
            template = self._published_artifact_template(conn, template_version_uid)
            owner = conn.execute("SELECT * FROM objects WHERE uid=?", (owner_object_uid,)).fetchone()
            if not owner:
                raise ContainerError("container.object.not_found", object_uid=owner_object_uid)
            self._require_action(conn, context, ActionCode.CREATE_ARTIFACT, ReferenceKind.OBJECT, owner_object_uid, owner)
            roles = {row[0] for row in conn.execute("SELECT role_code FROM template_create_roles WHERE template_version_uid=?", (template_version_uid,))}
            if not self._actor_allowed(context, roles):
                raise ContainerError("container.authorization.create_denied", template_version_uid=template_version_uid)
            artifact_uid = self._uid()
            conn.execute("""INSERT INTO artifacts(uid,template_version_uid,owner_object_uid,state,revision,immutable,created_by)
                         VALUES(?,?,?,?,?,?,?)""", (artifact_uid, template_version_uid, owner_object_uid, template["initial_state"], 1, 0, context.user_id))
            self._store_values(conn, template_version_uid, artifact_uid, values, replace=True, actor_id=context.user_id, aggregate_kind="artifact")
            self._audit(conn, "artifact.created", artifact_uid, context.user_id)
        self._publish("domain.container.artifact.created.v1", artifact_uid, context)
        return self.get_artifact(context, artifact_uid)

    def get_artifact(self, actor: object, artifact_uid: str) -> Artifact:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact_uid,)).fetchone()
            if row is not None:
                self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, artifact_uid, row)
        if row is None:
            raise ContainerError("container.artifact.not_found", artifact_uid=artifact_uid)
        return self._artifact_from_row(row)

    def get_artifact_detail(self, actor: object, artifact_uid: str) -> ArtifactDetail:
        context = self._actor(actor)
        entity = self.get_artifact(context, artifact_uid)
        with self._repository.read() as conn:
            values = self._read_visible_values(conn, "artifact", artifact_uid)
            refs = tuple(self.list_references(context, kind=ReferenceKind.ARTIFACT, uid=artifact_uid))
            files = tuple(self.list_artifact_files(context, artifact_uid))
            decisions = self.allowed_actions(context, ReferenceKind.ARTIFACT, artifact_uid)
        return ArtifactDetail(entity, values, decisions, refs, files)

    def update_artifact_fields(self, actor: object, artifact_uid: str, values: dict[str, object], *, expected_revision: int) -> Artifact:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            artifact = self._mutable_artifact(conn, artifact_uid, expected_revision)
            self._require_action(conn, context, ActionCode.UPDATE, ReferenceKind.ARTIFACT, artifact_uid, artifact)
            self._store_values(conn, artifact["template_version_uid"], artifact_uid, values, replace=False, actor_id=context.user_id, aggregate_kind="artifact")
            conn.execute("UPDATE artifacts SET revision=revision+1 WHERE uid=?", (artifact_uid,))
            self._audit(conn, "artifact.fields.updated", artifact_uid, context.user_id)
        self._publish("domain.container.artifact.updated.v1", artifact_uid, context)
        return self.get_artifact(context, artifact_uid)

    def add_artifact_file(self, actor: object, artifact_uid: str, content: bytes | BinaryIO, *, original_name: str, media_type: str, expected_revision: int) -> ArtifactFile:
        context = self._actor(actor)
        storage = self._storage()
        safe_original_name = self._safe_original_name(original_name)
        safe_media_type = self._safe_media_type(media_type)
        stored = None
        try:
            with self._repository.transaction() as conn:
                self._mutable_artifact(conn, artifact_uid, expected_revision)
                self._require_action(conn, context, ActionCode.UPDATE, ReferenceKind.ARTIFACT, artifact_uid)
                stored = storage.store(artifact_uid, content)
                file_uid = self._uid()
                conn.execute("""INSERT INTO artifact_files(uid,artifact_uid,relative_path,original_name,media_type,size_bytes,content_hash,immutable,created_by)
                             VALUES(?,?,?,?,?,?,?,?,?)""", (file_uid, artifact_uid, stored.relative_path, safe_original_name, safe_media_type, stored.size_bytes, stored.content_hash, 0, context.user_id))
                conn.execute("UPDATE artifacts SET revision=revision+1 WHERE uid=?", (artifact_uid,))
                self._audit(conn, "artifact.file.added", artifact_uid, context.user_id)
        except Exception:
            if stored is not None:
                storage.remove(stored.relative_path)
            raise
        self._publish("domain.container.artifact.file_added.v1", artifact_uid, context)
        return self.get_artifact_file(context, file_uid)

    def list_artifact_files(self, actor: object, artifact_uid: str) -> list[ArtifactFile]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            artifact = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact_uid,)).fetchone()
            if artifact is None: raise ContainerError("container.artifact.not_found", artifact_uid=artifact_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, artifact_uid, artifact)
            rows = conn.execute("SELECT * FROM artifact_files WHERE artifact_uid=? ORDER BY created_at, uid", (artifact_uid,)).fetchall()
        return [self._artifact_file_from_row(row) for row in rows]

    def get_artifact_file(self, actor: object, file_uid: str) -> ArtifactFile:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = conn.execute("SELECT * FROM artifact_files WHERE uid=?", (file_uid,)).fetchone()
            if row is not None:
                artifact = conn.execute("SELECT * FROM artifacts WHERE uid=?", (row["artifact_uid"],)).fetchone()
                self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, row["artifact_uid"], artifact)
        if row is None:
            raise ContainerError("container.artifact_file.not_found", file_uid=file_uid)
        return self._artifact_file_from_row(row)

    def read_artifact_file(self, actor: object, artifact_uid: str, file_uid: str) -> bytes:
        context = self._actor(actor)
        with self._repository.read() as conn:
            artifact = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact_uid,)).fetchone()
            if artifact is None: raise ContainerError("container.artifact.not_found", artifact_uid=artifact_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, artifact_uid, artifact)
            row = conn.execute("SELECT * FROM artifact_files WHERE uid=? AND artifact_uid=?", (file_uid, artifact_uid)).fetchone()
        if row is None:
            raise ContainerError("container.artifact_file.not_found", file_uid=file_uid)
        return self._storage().read(row["relative_path"], expected_hash=row["content_hash"], expected_size=row["size_bytes"])

    def finalize_artifact(self, actor: object, artifact_uid: str, *, expected_revision: int) -> ArtifactSnapshot:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            artifact = self._mutable_artifact(conn, artifact_uid, expected_revision)
            self._require_action(conn, context, ActionCode.FINALIZE, ReferenceKind.ARTIFACT, artifact_uid, artifact)
            files = conn.execute("SELECT * FROM artifact_files WHERE artifact_uid=? ORDER BY uid", (artifact_uid,)).fetchall()
            for file_row in files:
                self._storage().read(file_row["relative_path"], expected_hash=file_row["content_hash"], expected_size=file_row["size_bytes"])
            snapshot_uid = self._uid()
            state_hash = self._snapshot_hash(conn, artifact, files)
            conn.execute("""INSERT INTO artifact_snapshots(uid,artifact_uid,state_hash,template_version_uid,artifact_state,artifact_revision)
                         VALUES(?,?,?,?,?,?)""", (snapshot_uid, artifact_uid, state_hash, artifact["template_version_uid"], artifact["state"], artifact["revision"]))
            conn.execute("""INSERT INTO artifact_snapshot_field_values(snapshot_uid,field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value)
                         SELECT ?,field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value FROM artifact_field_values WHERE artifact_uid=?""", (snapshot_uid, artifact_uid))
            for file_row in files:
                conn.execute("""INSERT INTO artifact_snapshot_files(snapshot_uid,artifact_file_uid,relative_path,original_name,media_type,size_bytes,content_hash)
                             VALUES(?,?,?,?,?,?,?)""", (snapshot_uid, file_row["uid"], file_row["relative_path"], file_row["original_name"], file_row["media_type"], file_row["size_bytes"], file_row["content_hash"]))
            for reference in conn.execute("SELECT * FROM references_table WHERE source_uid=? OR target_uid=? ORDER BY uid", (artifact_uid, artifact_uid)):
                conn.execute("""INSERT INTO artifact_snapshot_references(snapshot_uid,reference_uid,source_kind,source_uid,target_kind,target_uid,link_type_uid)
                             VALUES(?,?,?,?,?,?,?)""", (snapshot_uid, reference["uid"], reference["source_kind"], reference["source_uid"], reference["target_kind"], reference["target_uid"], reference["link_type_uid"]))
            conn.execute("UPDATE artifact_files SET immutable=1 WHERE artifact_uid=?", (artifact_uid,))
            conn.execute("UPDATE artifacts SET immutable=1, final_snapshot_uid=?, finalized_at=CURRENT_TIMESTAMP, revision=revision+1 WHERE uid=?", (snapshot_uid, artifact_uid))
            self._audit(conn, "artifact.finalized", artifact_uid, context.user_id)
        self._publish("domain.container.artifact.finalized.v1", artifact_uid, context)
        return ArtifactSnapshot(snapshot_uid, artifact_uid, state_hash, artifact["template_version_uid"])

    def sign_artifact(self, actor: object, artifact_uid: str, *, meaning: str) -> ArtifactSignature:
        context = self._actor(actor)
        if not meaning.strip():
            raise ContainerError("container.signature.meaning_required")
        with self._repository.transaction() as conn:
            artifact = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact_uid,)).fetchone()
            if artifact is None:
                raise ContainerError("container.artifact.not_found", artifact_uid=artifact_uid)
            self._require_action(conn, context, ActionCode.SIGN, ReferenceKind.ARTIFACT, artifact_uid, artifact)
            if not artifact["immutable"] or not artifact["final_snapshot_uid"]:
                raise ContainerError("container.artifact.not_finalized", artifact_uid=artifact_uid)
            snapshot = conn.execute("SELECT * FROM artifact_snapshots WHERE uid=?", (artifact["final_snapshot_uid"],)).fetchone()
            signature_uid = self._uid()
            try:
                conn.execute("""INSERT INTO signatures(uid,artifact_uid,snapshot_uid,state_hash,signer_user_id,meaning)
                             VALUES(?,?,?,?,?,?)""", (signature_uid, artifact_uid, snapshot["uid"], snapshot["state_hash"], context.user_id, meaning.strip()))
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    raise ContainerError("container.signature.duplicate", artifact_uid=artifact_uid) from exc
                raise
            self._audit(conn, "artifact.signed", artifact_uid, context.user_id)
        self._publish("domain.container.artifact.signed.v1", artifact_uid, context)
        return ArtifactSignature(signature_uid, artifact_uid, snapshot["uid"], snapshot["state_hash"], context.user_id, meaning.strip())

    def correct_artifact(self, actor: object, artifact_uid: str) -> Artifact:
        context = self._actor(actor)
        storage = self._storage()
        created_paths: list[str] = []
        try:
            with self._repository.transaction() as conn:
                source = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact_uid,)).fetchone()
                if source is None:
                    raise ContainerError("container.artifact.not_found", artifact_uid=artifact_uid)
                if not source["immutable"]:
                    raise ContainerError("container.artifact.correction_requires_finalized", artifact_uid=artifact_uid)
                self._require_action(conn, context, ActionCode.CORRECT, ReferenceKind.ARTIFACT, artifact_uid, source)
                roles = {row[0] for row in conn.execute("SELECT role_code FROM template_create_roles WHERE template_version_uid=?", (source["template_version_uid"],))}
                if not self._actor_allowed(context, roles):
                    raise ContainerError("container.authorization.create_denied", template_version_uid=source["template_version_uid"])
                corrected_uid = self._uid()
                conn.execute("""INSERT INTO artifacts(uid,template_version_uid,owner_object_uid,state,revision,immutable,created_by)
                             VALUES(?,?,?,?,?,?,?)""", (corrected_uid, source["template_version_uid"], source["owner_object_uid"], source["state"], 1, 0, context.user_id))
                conn.execute("""INSERT INTO artifact_field_values(artifact_uid,field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value)
                             SELECT ?,field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value FROM artifact_field_values WHERE artifact_uid=?""", (corrected_uid, artifact_uid))
                for file_row in conn.execute("SELECT * FROM artifact_files WHERE artifact_uid=? ORDER BY uid", (artifact_uid,)):
                    content = storage.read(file_row["relative_path"], expected_hash=file_row["content_hash"], expected_size=file_row["size_bytes"])
                    stored = storage.store(corrected_uid, content)
                    created_paths.append(stored.relative_path)
                    conn.execute("""INSERT INTO artifact_files(uid,artifact_uid,relative_path,original_name,media_type,size_bytes,content_hash,immutable,created_by)
                                 VALUES(?,?,?,?,?,?,?,?,?)""", (self._uid(), corrected_uid, stored.relative_path, file_row["original_name"], file_row["media_type"], stored.size_bytes, stored.content_hash, 0, context.user_id))
                conn.execute("INSERT INTO artifact_corrections(corrected_artifact_uid,original_artifact_uid,created_by) VALUES(?,?,?)", (corrected_uid, artifact_uid, context.user_id))
                link = self._ensure_correction_link_type(conn, context.user_id)
                conn.execute("INSERT INTO references_table(uid,source_kind,source_uid,target_kind,target_uid,link_type_uid,created_by) VALUES(?,?,?,?,?,?,?)", (self._uid(), ReferenceKind.ARTIFACT.value, corrected_uid, ReferenceKind.ARTIFACT.value, artifact_uid, link["uid"], context.user_id))
                self._audit(conn, "artifact.corrected", corrected_uid, context.user_id)
        except Exception:
            for relative_path in created_paths:
                storage.remove(relative_path)
            raise
        self._publish("domain.container.artifact.corrected.v1", corrected_uid, context)
        return self.get_artifact(context, corrected_uid)

    def correction_source_uid(self, actor: object, corrected_artifact_uid: str) -> str | None:
        context = self._actor(actor)
        with self._repository.read() as conn:
            corrected = self._aggregate_row(conn, ReferenceKind.ARTIFACT, corrected_artifact_uid)
            if corrected is None: raise ContainerError("container.artifact.not_found", artifact_uid=corrected_artifact_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, corrected_artifact_uid, corrected)
            row = conn.execute("SELECT original_artifact_uid FROM artifact_corrections WHERE corrected_artifact_uid=?", (corrected_artifact_uid,)).fetchone()
            if row is not None:
                original = self._aggregate_row(conn, ReferenceKind.ARTIFACT, row["original_artifact_uid"])
                self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, row["original_artifact_uid"], original)
        return None if row is None else str(row["original_artifact_uid"])

    def allowed_actions(self, actor: object, kind: ReferenceKind, uid: str) -> dict[ActionCode, ActionDecision]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = self._aggregate_row(conn, kind, uid)
            if row is None: raise ContainerError(f"container.{kind.value.lower()}.not_found", uid=uid)
            return {action: self._decision(conn, context, action, kind, uid, row) for action in ActionCode}

    def create_link_type(self, actor: object, *, code: str, source_kind: ReferenceKind, target_kind: ReferenceKind, inverse_label: str | None = None) -> LinkType:
        context = self._actor(actor)
        self._require_template_admin(context)
        if not code or not code.replace("_", "").replace("-", "").isalnum(): raise ContainerError("container.link_type.invalid")
        with self._repository.transaction() as conn:
            if conn.execute("SELECT 1 FROM link_types WHERE code=?", (code,)).fetchone(): raise ContainerError("container.link_type.duplicate", code=code)
            uid = self._uid()
            conn.execute("INSERT INTO link_types(uid,code,source_kind,target_kind,inverse_label) VALUES(?,?,?,?,?)", (uid, code, source_kind.value, target_kind.value, inverse_label))
            self._audit(conn, "link_type.created", uid, context.user_id)
        return LinkType(uid, code, source_kind, target_kind, inverse_label)

    def create_reference(self, actor: object, *, source_kind: ReferenceKind, source_uid: str, target_kind: ReferenceKind, target_uid: str, link_type_uid: str) -> ContainerReference:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            link = conn.execute("SELECT * FROM link_types WHERE uid=?", (link_type_uid,)).fetchone()
            if link is None: raise ContainerError("container.reference.link_type_not_found", link_type_uid=link_type_uid)
            # Artifact -> Object has exactly one canonical representation: Object -> Artifact.
            if source_kind is ReferenceKind.ARTIFACT and target_kind is ReferenceKind.OBJECT:
                source_kind, source_uid, target_kind, target_uid = target_kind, target_uid, source_kind, source_uid
            if link["source_kind"] != source_kind.value or link["target_kind"] != target_kind.value:
                raise ContainerError("container.reference.kind_mismatch")
            source = self._aggregate_row(conn, source_kind, source_uid)
            target = self._aggregate_row(conn, target_kind, target_uid)
            if source is None or target is None: raise ContainerError("container.reference.target_not_found")
            self._require_action(conn, context, ActionCode.REFERENCE, source_kind, source_uid, source)
            self._require_action(conn, context, ActionCode.VIEW, target_kind, target_uid, target)
            uid = self._uid()
            try:
                conn.execute("INSERT INTO references_table(uid,source_kind,source_uid,target_kind,target_uid,link_type_uid,created_by) VALUES(?,?,?,?,?,?,?)", (uid, source_kind.value, source_uid, target_kind.value, target_uid, link_type_uid, context.user_id))
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc): raise ContainerError("container.reference.duplicate") from exc
                raise
            self._audit(conn, "reference.created", uid, context.user_id)
        self._publish("domain.container.reference.created.v1", uid, context)
        return ContainerReference(uid, source_kind, source_uid, target_kind, target_uid, link_type_uid)

    def list_references(self, actor: object, *, kind: ReferenceKind, uid: str) -> list[ContainerReference]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = self._aggregate_row(conn, kind, uid)
            if row is None: raise ContainerError("container.reference.target_not_found")
            self._require_action(conn, context, ActionCode.VIEW, kind, uid, row)
            rows = conn.execute("SELECT * FROM references_table WHERE (source_kind=? AND source_uid=?) OR (target_kind=? AND target_uid=?) ORDER BY uid", (kind.value, uid, kind.value, uid)).fetchall()
            result = []
            for reference in rows:
                source_kind, target_kind = ReferenceKind(reference["source_kind"]), ReferenceKind(reference["target_kind"])
                if self._decision(conn, context, ActionCode.VIEW, source_kind, reference["source_uid"]).allowed and self._decision(conn, context, ActionCode.VIEW, target_kind, reference["target_uid"]).allowed:
                    result.append(ContainerReference(reference["uid"], source_kind, reference["source_uid"], target_kind, reference["target_uid"], reference["link_type_uid"]))
            return result

    def create_external_reference(self, actor: object, *, source_kind: ReferenceKind, source_uid: str, provider_code: str, module_code: str, entity_uid: str, mode: ExternalReferenceMode, fixed_version_uid: str | None = None) -> ExternalReferenceTarget:
        context = self._actor(actor)
        if mode is ExternalReferenceMode.FIXED and (not fixed_version_uid or fixed_version_uid.strip().lower() == "latest"): raise ContainerError("container.external_reference.fixed_version_required")
        if mode is ExternalReferenceMode.DYNAMIC and fixed_version_uid: raise ContainerError("container.external_reference.dynamic_version_forbidden")
        with self._repository.transaction() as conn:
            source = self._aggregate_row(conn, source_kind, source_uid)
            if source is None: raise ContainerError("container.reference.target_not_found")
            self._require_action(conn, context, ActionCode.REFERENCE, source_kind, source_uid, source)
            uid = self._uid()
            conn.execute("INSERT INTO external_reference_targets(uid,source_kind,source_uid,provider_code,module_code,entity_uid,mode,fixed_version_uid,created_by) VALUES(?,?,?,?,?,?,?,?,?)", (uid, source_kind.value, source_uid, provider_code, module_code, entity_uid, mode.value, fixed_version_uid, context.user_id))
            self._audit(conn, "external_reference.created", uid, context.user_id)
        return ExternalReferenceTarget(uid, source_kind, source_uid, provider_code, module_code, entity_uid, mode, fixed_version_uid)

    def resolve_external_reference(self, actor: object, external_reference_uid: str) -> str:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            target = conn.execute("SELECT * FROM external_reference_targets WHERE uid=?", (external_reference_uid,)).fetchone()
            if target is None: raise ContainerError("container.external_reference.not_found")
            source_kind = ReferenceKind(target["source_kind"])
            self._require_action(conn, context, ActionCode.VIEW, source_kind, target["source_uid"])
            if target["mode"] == ExternalReferenceMode.FIXED.value: return target["fixed_version_uid"]
            if self._external_reference_resolver is None: raise ContainerError("container.external_reference.resolver_unavailable")
            version_uid = self._external_reference_resolver.resolve(provider_code=target["provider_code"], module_code=target["module_code"], entity_uid=target["entity_uid"])
            if not version_uid: raise ContainerError("container.external_reference.unresolved")
            conn.execute("INSERT INTO external_reference_resolutions(uid,external_reference_target_uid,resolved_version_uid,resolved_by) VALUES(?,?,?,?)", (self._uid(), external_reference_uid, version_uid, context.user_id))
            self._audit(conn, "external_reference.resolved", external_reference_uid, context.user_id)
        return str(version_uid)

    def list_external_reference_resolutions(self, actor: object, external_reference_uid: str) -> list[ExternalReferenceResolution]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            target = conn.execute("SELECT * FROM external_reference_targets WHERE uid=?", (external_reference_uid,)).fetchone()
            if target is None: raise ContainerError("container.external_reference.not_found")
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind(target["source_kind"]), target["source_uid"])
            rows = conn.execute("SELECT * FROM external_reference_resolutions WHERE external_reference_target_uid=? ORDER BY resolved_at,uid", (external_reference_uid,)).fetchall()
        return [ExternalReferenceResolution(row["uid"], row["external_reference_target_uid"], row["resolved_version_uid"], row["resolved_by"]) for row in rows]

    def transition_object(self, actor: object, object_uid: str, *, to_state: str, reason: str | None, expected_revision: int, signature_meaning: str | None = None) -> ContainerObject:
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None: raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.TRANSITION, ReferenceKind.OBJECT, object_uid, obj)
            if obj["revision"] != expected_revision: raise ContainerError("container.revision.conflict", expected=expected_revision, actual=obj["revision"])
            transition = conn.execute("SELECT * FROM lifecycle_transitions WHERE template_version_uid=? AND from_state_code=? AND to_state_code=?", (obj["template_version_uid"], obj["state"], to_state)).fetchone()
            if transition is None: raise ContainerError("container.lifecycle.invalid_transition")
            roles = {r[0] for r in conn.execute("SELECT role_code FROM lifecycle_transition_roles WHERE transition_uid=?", (transition["uid"],))}
            if roles and not self._actor_allowed(context, roles): raise ContainerError("container.lifecycle.role_denied")
            if transition["reason_required"] and not (reason or "").strip(): raise ContainerError("container.lifecycle.reason_required")
            if transition["signature_required"] and not (signature_meaning or "").strip(): raise ContainerError("container.lifecycle.signature_required")
            conn.execute("UPDATE objects SET state=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE uid=?", (to_state, object_uid))
            self._audit(conn, "object.transitioned", object_uid, context.user_id)
            if signature_meaning:
                self._create_object_signature(conn, context, self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid), signature_meaning)
        self._publish("domain.container.object.transitioned.v1", object_uid, context)
        return self.get_object(context, object_uid)

    def sign_object(self, actor: object, object_uid: str, *, meaning: str) -> ObjectSignature:
        context = self._actor(actor)
        if not meaning.strip(): raise ContainerError("container.signature.meaning_required")
        with self._repository.transaction() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None: raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.SIGN, ReferenceKind.OBJECT, object_uid, obj)
            result = self._create_object_signature(conn, context, obj, meaning)
            self._audit(conn, "object.signed", object_uid, context.user_id)
        self._publish("domain.container.object.signed.v1", object_uid, context)
        return result

    def list_object_signatures(self, actor: object, object_uid: str) -> list[ObjectSignature]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None: raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, object_uid, obj)
            rows = conn.execute("SELECT * FROM signatures WHERE object_uid=? ORDER BY signed_at,uid", (object_uid,)).fetchall()
        return [ObjectSignature(row["uid"], row["object_uid"], row["snapshot_uid"], row["state_hash"], row["signer_user_id"], row["meaning"]) for row in rows]

    def get_object_snapshot(self, actor: object, snapshot_uid: str) -> ObjectSnapshot:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = conn.execute("SELECT * FROM object_snapshots WHERE uid=?", (snapshot_uid,)).fetchone()
            if row is None: raise ContainerError("container.object_snapshot.not_found", snapshot_uid=snapshot_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, row["object_uid"])
        return ObjectSnapshot(row["uid"], row["object_uid"], row["state_hash"], row["object_revision"])

    def list_audit_records(self, actor: object, *, kind: ReferenceKind, uid: str) -> list[AuditRecord]:
        context = self._actor(actor)
        with self._repository.read() as conn:
            row = self._aggregate_row(conn, kind, uid)
            if row is None: raise ContainerError("container.authorization.not_found")
            self._require_action(conn, context, ActionCode.VIEW, kind, uid, row)
            rows = conn.execute("SELECT * FROM audit_events WHERE aggregate_uid=? ORDER BY occurred_at,uid", (uid,)).fetchall()
            details = {row["uid"]: tuple((detail["detail_key"], detail["detail_value"]) for detail in conn.execute("SELECT detail_key,detail_value FROM audit_event_details WHERE audit_event_uid=? ORDER BY detail_key", (row["uid"],))) for row in rows}
        return [AuditRecord(row["uid"], row["event_type"], row["aggregate_uid"], row["actor_user_id"], row["occurred_at"], details[row["uid"]]) for row in rows]

    def archive_object(self, actor: object, object_uid: str, *, expected_revision: int) -> ContainerObject:
        return self._set_archive(actor, object_uid, expected_revision=expected_revision, archived=True)

    def reactivate_object(self, actor: object, object_uid: str, *, expected_revision: int) -> ContainerObject:
        return self._set_archive(actor, object_uid, expected_revision=expected_revision, archived=False)

    def search_objects(self, actor: object, query: str, *, field_keys: tuple[str, ...] | None = None, include_archived: bool = False, limit: int = 100, offset: int = 0) -> list[ContainerObject]:
        context = self._actor(actor)
        if limit < 1 or limit > 100 or offset < 0: raise ContainerError("container.search.invalid_pagination")
        with self._repository.read() as conn:
            fields = field_keys or tuple(r[0] for r in conn.execute("SELECT DISTINCT field_key FROM field_definitions WHERE searchable=1"))
            if not fields: return []
            found = conn.execute("SELECT DISTINCT field_key FROM field_definitions WHERE searchable=1 AND field_key IN (%s)" % ",".join("?" * len(fields)), fields).fetchall()
            if {r[0] for r in found} != set(fields): raise ContainerError("container.search.non_searchable_field")
            searchable_value = "coalesce(v.string_value,CAST(v.integer_value AS TEXT),v.decimal_value,CAST(v.boolean_value AS TEXT),v.date_value,v.datetime_value,v.user_uid,v.object_uid_value,v.artifact_uid_value,'')"
            rows = conn.execute("SELECT DISTINCT o.* FROM objects o JOIN object_field_values v ON v.object_uid=o.uid JOIN field_definitions d ON d.uid=v.field_definition_uid WHERE d.searchable=1 AND d.field_key IN (%s) AND lower(%s) LIKE lower(?) %s ORDER BY o.uid" % (",".join("?" * len(fields)), searchable_value, "" if include_archived else "AND o.archived=0"), (*fields, f"%{query}%")).fetchall()
            permitted = [row for row in rows if self._decision(conn, context, ActionCode.SEARCH, ReferenceKind.OBJECT, row["uid"], row).allowed]
            return [self._object_from_row(row) for row in permitted[offset:offset + limit]]

    def export_object_subtree(self, actor: object, root_object_uid: str, *, include_artifacts: bool = True, include_files: bool = False, printable: bool = False) -> ExportBundle:
        """Create a deterministic, permission-complete subtree export.

        The intentionally fail-closed permission rule prevents a user that can
        see only a root from receiving a misleading partial export.
        """
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            bundle = self._build_export(conn, context, root_object_uid, include_artifacts=include_artifacts, include_files=include_files, printable=printable)
            self._audit(conn, "object.exported", root_object_uid, context.user_id, {"export_uid": bundle.record.uid, "manifest_hash": bundle.record.manifest_hash})
        self._publish("domain.container.object.exported.v1", root_object_uid, context)
        return bundle

    def store_export_as_artifact(self, actor: object, root_object_uid: str, artifact_template_version_uid: str, *, include_artifacts: bool = True, include_files: bool = True, printable: bool = False, values: dict[str, object] | None = None) -> ExportBundle:
        context = self._actor(actor)
        storage = self._storage()
        stored = None
        try:
            with self._repository.transaction() as conn:
                owner = self._aggregate_row(conn, ReferenceKind.OBJECT, root_object_uid)
                if owner is None:
                    raise ContainerError("container.object.not_found", object_uid=root_object_uid)
                self._require_action(conn, context, ActionCode.CREATE_ARTIFACT, ReferenceKind.OBJECT, root_object_uid, owner)
                bundle = self._build_export(conn, context, root_object_uid, include_artifacts=include_artifacts, include_files=include_files, printable=printable)
                template = self._published_artifact_template(conn, artifact_template_version_uid)
                roles = {row[0] for row in conn.execute("SELECT role_code FROM template_create_roles WHERE template_version_uid=?", (artifact_template_version_uid,))}
                if not self._actor_allowed(context, roles):
                    raise ContainerError("container.authorization.create_denied", template_version_uid=artifact_template_version_uid)
                artifact_uid = self._uid()
                conn.execute("INSERT INTO artifacts(uid,template_version_uid,owner_object_uid,state,revision,immutable,created_by) VALUES(?,?,?,?,?,?,?)", (artifact_uid, artifact_template_version_uid, root_object_uid, template["initial_state"], 1, 0, context.user_id))
                self._store_values(conn, artifact_template_version_uid, artifact_uid, values or {}, replace=True, actor_id=context.user_id, aggregate_kind="artifact")
                stored = storage.store(artifact_uid, bundle.zip_bytes)
                file_uid = self._uid()
                conn.execute("INSERT INTO artifact_files(uid,artifact_uid,relative_path,original_name,media_type,size_bytes,content_hash,immutable,created_by) VALUES(?,?,?,?,?,?,?,?,?)", (file_uid, artifact_uid, stored.relative_path, "container-export.zip", "application/zip", stored.size_bytes, stored.content_hash, 0, context.user_id))
                conn.execute("UPDATE artifacts SET revision=revision+1 WHERE uid=?", (artifact_uid,))
                link = conn.execute("SELECT * FROM link_types WHERE code='snapshot_of'").fetchone()
                if link is None:
                    link_uid = self._uid()
                    conn.execute("INSERT INTO link_types(uid,code,source_kind,target_kind,inverse_label) VALUES(?,?,?,?,?)", (link_uid, "snapshot_of", ReferenceKind.OBJECT.value, ReferenceKind.ARTIFACT.value, "has_snapshot"))
                elif link["source_kind"] != ReferenceKind.OBJECT.value or link["target_kind"] != ReferenceKind.ARTIFACT.value:
                    raise ContainerError("container.export.snapshot_link_type_conflict")
                else:
                    link_uid = link["uid"]
                conn.execute("INSERT INTO references_table(uid,source_kind,source_uid,target_kind,target_uid,link_type_uid,created_by) VALUES(?,?,?,?,?,?,?)", (self._uid(), ReferenceKind.OBJECT.value, root_object_uid, ReferenceKind.ARTIFACT.value, artifact_uid, link_uid, context.user_id))
                self._audit(conn, "export.stored_as_artifact", artifact_uid, context.user_id, {"export_uid": bundle.record.uid, "file_uid": file_uid, "root_object_uid": root_object_uid})
                bundle = ExportBundle(bundle.record, bundle.manifest, bundle.zip_bytes, bundle.printable_text, artifact_uid)
        except Exception:
            if stored is not None:
                storage.remove(stored.relative_path)
            raise
        self._publish("domain.container.export.stored.v1", artifact_uid, context)
        return bundle

    def migrate_object_template(self, actor: object, object_uid: str, target_published_version_uid: str, *, expected_revision: int, values_for_new_required: dict[str, object] | None = None) -> TemplateMigrationRecord:
        context = self._actor(actor)
        supplied = values_for_new_required or {}
        with self._repository.transaction() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None:
                raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.UPDATE, ReferenceKind.OBJECT, object_uid, obj)
            if obj["revision"] != expected_revision:
                raise ContainerError("container.revision.conflict", expected=expected_revision, actual=obj["revision"])
            if obj["archived"] or obj["fixed"]:
                raise ContainerError("container.template_migration.read_only", object_uid=object_uid)
            target = self._published_object_template(conn, target_published_version_uid)
            old = conn.execute("SELECT * FROM template_versions WHERE uid=?", (obj["template_version_uid"],)).fetchone()
            if target["template_uid"] != old["template_uid"]:
                raise ContainerError("container.template_migration.template_mismatch")
            if target["uid"] == old["uid"]:
                raise ContainerError("container.template_migration.same_version")
            old_values = {row["field_key"]: row for row in conn.execute("SELECT d.field_key,d.field_type,v.* FROM object_field_values v JOIN field_definitions d ON d.uid=v.field_definition_uid WHERE v.object_uid=?", (object_uid,))}
            target_defs = {row["field_key"]: row for row in conn.execute("SELECT * FROM field_definitions WHERE template_version_uid=?", (target_published_version_uid,))}
            unknown = set(supplied) - set(target_defs)
            if unknown:
                raise ContainerError("container.field.unknown", fields=sorted(unknown))
            migrated_values: dict[str, object] = {}
            for key, definition in target_defs.items():
                old_value = old_values.get(key)
                if old_value is not None and old_value["field_type"] == definition["field_type"]:
                    migrated_values[key] = self._decode_value(old_value, FieldType(definition["field_type"]))
            migrated_values.update(supplied)
            missing = [key for key, definition in target_defs.items() if definition["required"] and key not in migrated_values]
            if missing:
                raise ContainerError("container.template_migration.required_values", fields=sorted(missing))
            record_uid = self._uid()
            conn.execute("INSERT INTO template_migrations(uid,object_uid,old_template_version_uid,new_template_version_uid,migrated_by) VALUES(?,?,?,?,?)", (record_uid, object_uid, old["uid"], target["uid"], context.user_id))
            for key, definition in target_defs.items():
                source = old_values.get(key)
                conn.execute("INSERT INTO template_migration_fields(template_migration_uid,field_key,old_field_definition_uid,new_field_definition_uid,was_compatible) VALUES(?,?,?,?,?)", (record_uid, key, source["field_definition_uid"] if source else None, definition["uid"], int(source is not None and source["field_type"] == definition["field_type"])))
            conn.execute("DELETE FROM object_field_values WHERE object_uid=?", (object_uid,))
            self._store_values(conn, target["uid"], object_uid, migrated_values, replace=True, actor_id=context.user_id)
            conn.execute("UPDATE objects SET template_version_uid=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE uid=?", (target["uid"], object_uid))
            self._audit(conn, "object.template.migrated", object_uid, context.user_id, {"migration_uid": record_uid, "old_template_version_uid": old["uid"], "new_template_version_uid": target["uid"]})
        self._publish("domain.container.object.template_migrated.v1", object_uid, context)
        return TemplateMigrationRecord(record_uid, object_uid, old["uid"], target["uid"], context.user_id)

    def configure_deletion_policy(self, actor: object, *, allowed_role_codes: tuple[str, ...], require_backup: bool, require_second_approver: bool, template_version_uid: str | None = None) -> DeletionPolicy:
        context = self._actor(actor)
        self._require_template_admin(context)
        roles = tuple(sorted({role.strip().upper() for role in allowed_role_codes if role.strip()}))
        if not roles:
            raise ContainerError("container.deletion.invalid_policy")
        with self._repository.transaction() as conn:
            if template_version_uid is not None:
                template = conn.execute("SELECT kind FROM template_versions WHERE uid=?", (template_version_uid,)).fetchone()
                if template is None or template["kind"] != TemplateKind.OBJECT.value:
                    raise ContainerError("container.template.not_found", template_version_uid=template_version_uid)
                scope, scope_key = DeletionPolicyScope.TEMPLATE, template_version_uid
            else:
                scope, scope_key = DeletionPolicyScope.GLOBAL, ""
            conn.execute("DELETE FROM deletion_policy_roles WHERE policy_uid IN (SELECT uid FROM deletion_policies WHERE scope=? AND scope_key=?)", (scope.value, scope_key))
            conn.execute("DELETE FROM deletion_policies WHERE scope=? AND scope_key=?", (scope.value, scope_key))
            policy_uid = self._uid()
            conn.execute("INSERT INTO deletion_policies(uid,scope,scope_key,template_version_uid,require_backup,require_second_approver,configured_by) VALUES(?,?,?,?,?,?,?)", (policy_uid, scope.value, scope_key, template_version_uid, int(require_backup), int(require_second_approver), context.user_id))
            for role in roles:
                conn.execute("INSERT INTO deletion_policy_roles(policy_uid,role_code) VALUES(?,?)", (policy_uid, role))
            self._audit(conn, "deletion.policy.configured", policy_uid, context.user_id, {"scope": scope.value, "template_version_uid": template_version_uid or ""})
        self._publish("domain.container.deletion.policy_configured.v1", policy_uid, context)
        return DeletionPolicy(policy_uid, scope, template_version_uid, roles, require_backup, require_second_approver)

    def create_backup_evidence(self, actor: object, *, scope_uid: str, integrity_hash: str) -> BackupEvidence:
        context = self._actor(actor)
        self._require_deletion_governance_actor(context)
        if not scope_uid or len(integrity_hash) != 64 or any(char not in "0123456789abcdefABCDEF" for char in integrity_hash):
            raise ContainerError("container.deletion.invalid_backup_evidence")
        with self._repository.transaction() as conn:
            scope = self._aggregate_row(conn, ReferenceKind.OBJECT, scope_uid)
            if scope is None:
                raise ContainerError("container.object.not_found", object_uid=scope_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, scope_uid, scope)
            uid = self._uid()
            conn.execute("INSERT INTO backup_evidence(uid,scope_uid,integrity_hash,created_by) VALUES(?,?,?,?)", (uid, scope_uid, integrity_hash.lower(), context.user_id))
            self._audit(conn, "backup.evidence.created", uid, context.user_id, {"scope_uid": scope_uid, "integrity_hash": integrity_hash.lower()})
        return BackupEvidence(uid, scope_uid, integrity_hash.lower(), context.user_id)

    def approve_physical_deletion(self, actor: object, *, object_uid: str, requester_user_id: str) -> PhysicalDeletionApproval:
        context = self._actor(actor)
        self._require_deletion_governance_actor(context)
        if not requester_user_id or requester_user_id == context.user_id:
            raise ContainerError("container.deletion.approver_must_differ")
        with self._repository.transaction() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None:
                raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, object_uid, obj)
            uid = self._uid()
            conn.execute("INSERT INTO physical_deletion_approvals(uid,object_uid,requester_user_id,approved_by) VALUES(?,?,?,?)", (uid, object_uid, requester_user_id, context.user_id))
            self._audit(conn, "deletion.approved", object_uid, context.user_id, {"approval_uid": uid, "requester_user_id": requester_user_id})
        return PhysicalDeletionApproval(uid, object_uid, requester_user_id, context.user_id)

    def physical_delete_object(self, actor: object, object_uid: str, *, reason: str, backup_evidence_uid: str | None = None, approval_uid: str | None = None) -> Tombstone:
        context = self._actor(actor)
        if not reason.strip():
            raise ContainerError("container.deletion.reason_required")
        with self._repository.transaction() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None:
                raise ContainerError("container.object.not_found", object_uid=object_uid)
            policy = self._matching_deletion_policy(conn, obj["template_version_uid"])
            decision = self._deletion_decision(conn, context, obj, policy)
            if not decision.allowed:
                raise ContainerError(decision.denial_code or "container.deletion.policy_required", **decision.params)
            if policy["require_backup"]:
                backup = conn.execute("SELECT * FROM backup_evidence WHERE uid=? AND scope_uid=?", (backup_evidence_uid, object_uid)).fetchone()
                if backup is None:
                    raise ContainerError("container.deletion.backup_required")
            else:
                backup = None
            if policy["require_second_approver"]:
                approval = conn.execute("SELECT * FROM physical_deletion_approvals WHERE uid=? AND object_uid=? AND requester_user_id=?", (approval_uid, object_uid, context.user_id)).fetchone()
                if approval is None or approval["approved_by"] == context.user_id:
                    raise ContainerError("container.deletion.approval_required")
            else:
                approval = None
            tombstone_uid = self._uid()
            conn.execute("INSERT INTO tombstones(uid,deleted_entity_uid,deleted_entity_kind,backup_evidence_uid,deletion_approval_uid,deleted_by,reason) VALUES(?,?,?,?,?,?,?)", (tombstone_uid, object_uid, ReferenceKind.OBJECT.value, backup["uid"] if backup else None, approval["uid"] if approval else None, context.user_id, reason.strip()))
            self._audit(conn, "object.physically_deleted", object_uid, context.user_id, {"tombstone_uid": tombstone_uid, "reason": reason.strip(), "backup_evidence_uid": backup["uid"] if backup else "", "approval_uid": approval["uid"] if approval else ""})
            conn.execute("DELETE FROM objects WHERE uid=?", (object_uid,))
        self._publish("domain.container.object.physically_deleted.v1", object_uid, context)
        return Tombstone(tombstone_uid, object_uid, ReferenceKind.OBJECT.value, backup["uid"] if backup else None, approval["uid"] if approval else None, context.user_id, reason.strip())

    def list_tombstones(self, actor: object) -> list[Tombstone]:
        context = self._actor(actor)
        self._require_template_admin(context)
        with self._repository.read() as conn:
            rows = conn.execute("SELECT * FROM tombstones ORDER BY deleted_at,uid").fetchall()
        return [Tombstone(row["uid"], row["deleted_entity_uid"], row["deleted_entity_kind"], row["backup_evidence_uid"], row["deletion_approval_uid"], row["deleted_by"], row["reason"]) for row in rows]

    def workspace_root_uid(self) -> str:
        with self._repository.read() as conn:
            row = conn.execute("SELECT uid FROM workspace_roots").fetchone()
        if row is None:
            raise ContainerError("container.workspace.missing_root")
        return str(row["uid"])

    def _build_export(self, conn, context, root_object_uid, *, include_artifacts, include_files, printable):
        root = self._aggregate_row(conn, ReferenceKind.OBJECT, root_object_uid)
        if root is None:
            raise ContainerError("container.object.not_found", object_uid=root_object_uid)
        self._require_action(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, root_object_uid, root)
        object_rows = conn.execute("WITH RECURSIVE t(uid) AS (SELECT uid FROM objects WHERE uid=? UNION ALL SELECT o.uid FROM objects o JOIN t ON o.parent_kind='OBJECT' AND o.parent_uid=t.uid) SELECT * FROM objects WHERE uid IN (SELECT uid FROM t) ORDER BY uid", (root_object_uid,)).fetchall()
        for row in object_rows:
            if not self._decision(conn, context, ActionCode.VIEW, ReferenceKind.OBJECT, row["uid"], row).allowed:
                raise ContainerError("container.export.incomplete_permissions", uid=row["uid"])
        object_uids = tuple(row["uid"] for row in object_rows)
        artifact_rows = []
        if include_artifacts and object_uids:
            placeholders = ",".join("?" * len(object_uids))
            artifact_rows = conn.execute(f"SELECT * FROM artifacts WHERE owner_object_uid IN ({placeholders}) ORDER BY uid", object_uids).fetchall()
            for row in artifact_rows:
                if not self._decision(conn, context, ActionCode.VIEW, ReferenceKind.ARTIFACT, row["uid"], row).allowed:
                    raise ContainerError("container.export.incomplete_permissions", uid=row["uid"])
        artifact_uids = tuple(row["uid"] for row in artifact_rows)
        file_rows = []
        if include_files and artifact_uids:
            placeholders = ",".join("?" * len(artifact_uids))
            file_rows = conn.execute(f"SELECT * FROM artifact_files WHERE artifact_uid IN ({placeholders}) ORDER BY uid", artifact_uids).fetchall()
        objects = [{"uid": row["uid"], "template_version_uid": row["template_version_uid"], "parent_kind": row["parent_kind"], "parent_uid": row["parent_uid"], "state": row["state"], "revision": row["revision"], "archived": bool(row["archived"])} for row in object_rows]
        artifacts = [{"uid": row["uid"], "template_version_uid": row["template_version_uid"], "owner_object_uid": row["owner_object_uid"], "state": row["state"], "revision": row["revision"], "immutable": bool(row["immutable"]), "final_snapshot_uid": row["final_snapshot_uid"]} for row in artifact_rows]
        files = [{"uid": row["uid"], "artifact_uid": row["artifact_uid"], "original_name": row["original_name"], "media_type": row["media_type"], "size_bytes": row["size_bytes"], "content_hash": row["content_hash"]} for row in file_rows]
        created_at = str(root["created_at"])
        manifest = {"schema_version": 1, "module_version": "1.0.0", "root_object_uid": root_object_uid, "object_uids": [row["uid"] for row in object_rows], "artifact_uids": [row["uid"] for row in artifact_rows], "file_uids": [row["uid"] for row in file_rows], "objects": objects, "artifacts": artifacts, "files": files, "include_artifacts": include_artifacts, "include_files": include_files, "printable": printable, "actor_user_id": context.user_id, "created_at": created_at}
        manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        printable_text = self._printable_export(conn, object_rows, artifact_rows) if printable else None
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
            self._zip_write(bundle, "manifest.json", manifest_bytes)
            if printable_text is not None:
                self._zip_write(bundle, "printable.txt", printable_text.encode("utf-8"))
            if include_files:
                for row in file_rows:
                    self._zip_write(bundle, f"files/{row['uid']}", self._storage().read(row["relative_path"], expected_hash=row["content_hash"], expected_size=row["size_bytes"]))
        record_uid = self._uid()
        conn.execute("INSERT INTO exports(uid,root_object_uid,manifest_hash,created_by,include_artifacts,include_files,printable) VALUES(?,?,?,?,?,?,?)", (record_uid, root_object_uid, manifest_hash, context.user_id, int(include_artifacts), int(include_files), int(printable)))
        for uid in object_uids:
            conn.execute("INSERT INTO export_items(export_uid,item_kind,item_uid,content_hash) VALUES(?,?,?,NULL)", (record_uid, ReferenceKind.OBJECT.value, uid))
        for row in artifact_rows:
            conn.execute("INSERT INTO export_items(export_uid,item_kind,item_uid,content_hash) VALUES(?,?,?,NULL)", (record_uid, ReferenceKind.ARTIFACT.value, row["uid"]))
        for row in file_rows:
            conn.execute("INSERT INTO export_items(export_uid,item_kind,item_uid,content_hash) VALUES(?,?,?,?)", (record_uid, "FILE", row["uid"], row["content_hash"]))
        record = ExportRecord(record_uid, root_object_uid, manifest_hash, context.user_id, include_artifacts, include_files, printable)
        return ExportBundle(record, manifest, archive.getvalue(), printable_text)

    def _printable_export(self, conn, object_rows, artifact_rows):
        lines = ["Container export"]
        for kind, rows, owner_column in (("Object", object_rows, "object_uid"), ("Artifact", artifact_rows, "artifact_uid")):
            for row in rows:
                lines.append(f"{kind} {row['uid']}")
                values = conn.execute(f"SELECT d.field_key,d.field_type,v.* FROM {owner_column.split('_')[0]}_field_values v JOIN field_definitions d ON d.uid=v.field_definition_uid WHERE v.{owner_column}=? AND d.visible=1 AND d.printable=1 ORDER BY d.field_key", (row["uid"],)).fetchall()
                for value in values:
                    lines.append(f"{value['field_key']}: {self._safe_print_value(self._decode_value(value, FieldType(value['field_type'])))}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _zip_write(bundle, name, content):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        bundle.writestr(info, content)

    @staticmethod
    def _safe_print_value(value):
        text = ", ".join(value) if isinstance(value, tuple) else str(value)
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text

    @staticmethod
    def _decode_value(row, field_type):
        if field_type in {FieldType.STRING, FieldType.MULTILINE_TEXT, FieldType.SINGLE_SELECT}:
            return row["string_value"]
        if field_type is FieldType.MULTI_SELECT:
            return tuple((row["string_value"] or "").split("\x1f"))
        if field_type is FieldType.INTEGER:
            return row["integer_value"]
        if field_type is FieldType.DECIMAL:
            return row["decimal_value"]
        if field_type is FieldType.BOOLEAN:
            return bool(row["boolean_value"])
        if field_type is FieldType.DATE:
            return row["date_value"]
        if field_type is FieldType.DATETIME:
            return row["datetime_value"]
        if field_type is FieldType.USER_REFERENCE:
            return row["user_uid"]
        if field_type is FieldType.OBJECT_REFERENCE:
            return row["object_uid_value"]
        return row["artifact_uid_value"]

    def _matching_deletion_policy(self, conn, template_version_uid):
        return conn.execute("SELECT * FROM deletion_policies WHERE scope='TEMPLATE' AND scope_key=?", (template_version_uid,)).fetchone() or conn.execute("SELECT * FROM deletion_policies WHERE scope='GLOBAL' AND scope_key='' ").fetchone()

    def _deletion_decision(self, conn, context, row, policy=None):
        policy = policy if policy is not None else self._matching_deletion_policy(conn, row["template_version_uid"])
        if policy is None:
            return ActionDecision(False, "container.deletion.policy_required")
        roles = {entry[0] for entry in conn.execute("SELECT role_code FROM deletion_policy_roles WHERE policy_uid=?", (policy["uid"],))}
        if not self._actor_allowed(context, roles):
            return ActionDecision(False, "container.deletion.role_denied")
        if not row["archived"]:
            return ActionDecision(False, "container.deletion.requires_archived")
        if any((
            conn.execute("SELECT 1 FROM objects WHERE parent_kind='OBJECT' AND parent_uid=?", (row["uid"],)).fetchone(),
            conn.execute("SELECT 1 FROM artifacts WHERE owner_object_uid=?", (row["uid"],)).fetchone(),
            conn.execute("SELECT 1 FROM references_table WHERE (source_kind='OBJECT' AND source_uid=?) OR (target_kind='OBJECT' AND target_uid=?)", (row["uid"], row["uid"])).fetchone(),
            conn.execute("SELECT 1 FROM external_reference_targets WHERE source_kind='OBJECT' AND source_uid=?", (row["uid"],)).fetchone(),
            conn.execute("SELECT 1 FROM object_field_values WHERE object_uid=?", (row["uid"],)).fetchone(),
            conn.execute("SELECT 1 FROM object_snapshots WHERE object_uid=?", (row["uid"],)).fetchone(),
            conn.execute("SELECT 1 FROM signatures WHERE object_uid=?", (row["uid"],)).fetchone(),
            conn.execute("SELECT 1 FROM exports WHERE root_object_uid=?", (row["uid"],)).fetchone(),
        )):
            return ActionDecision(False, "container.deletion.nonempty_leaf_unsupported")
        return ActionDecision(True, params={"require_backup": bool(policy["require_backup"]), "require_second_approver": bool(policy["require_second_approver"]), "policy_uid": policy["uid"]})

    def _insert_object(self, conn, actor_id, template, parent, depth, values, *, fixed, events):
        if depth > MAX_OBJECT_DEPTH:
            raise ContainerError("container.tree.max_depth", max_depth=MAX_OBJECT_DEPTH)
        self._assert_child_cardinality(conn, parent, template["uid"])
        object_uid = self._uid()
        conn.execute("""INSERT INTO objects(uid,template_version_uid,parent_kind,parent_uid,depth,state,revision,fixed,created_by)
                     VALUES(?,?,?,?,?,?,?,?,?)""", (object_uid, template["uid"], parent.kind.value, parent.uid, depth, template["initial_state"], 1, int(fixed), actor_id))
        self._store_values(conn, template["uid"], object_uid, values, replace=True, actor_id=actor_id)
        self._audit(conn, "object.created", object_uid, actor_id)
        events.append(("domain.container.object.created.v1", object_uid))
        for child in self._children(conn, template["uid"]):
            if child["auto_create"] or child["min_count"] > 0:
                child_template = self._published_object_template(conn, child["child_template_version_uid"])
                count = max(1 if child["auto_create"] else 0, child["min_count"])
                for _ in range(count):
                    self._insert_object(conn, actor_id, child_template, StructuralParentRef(ParentKind.OBJECT, object_uid), depth + 1, {}, fixed=child["mode"] == ChildMode.FIXED.value, events=events)
        return ContainerObject(object_uid, template["uid"], parent, depth, 1, template["initial_state"], fixed)

    def _store_values(self, conn, template_uid, aggregate_uid, values, *, replace, actor_id, aggregate_kind="object"):
        value_table = "object_field_values" if aggregate_kind == "object" else "artifact_field_values"
        history_table = "object_field_value_history" if aggregate_kind == "object" else "artifact_field_value_history"
        owner_column = "object_uid" if aggregate_kind == "object" else "artifact_uid"
        definitions = {row["field_key"]: row for row in conn.execute("SELECT * FROM field_definitions WHERE template_version_uid=?", (template_uid,))}
        unknown = set(values) - set(definitions)
        if unknown:
            raise ContainerError("container.field.unknown", fields=sorted(unknown))
        if replace:
            missing = [key for key, definition in definitions.items() if definition["required"] and key not in values]
            if missing:
                raise ContainerError("container.field.required", fields=missing)
        for key, value in values.items():
            definition = definitions[key]
            if not definition["editable"] and not replace:
                raise ContainerError("container.field.not_editable", field=key)
            encoded = self._typed_value(conn, definition, value)
            conn.execute(f"DELETE FROM {value_table} WHERE {owner_column}=? AND field_definition_uid=?", (aggregate_uid, definition["uid"]))
            conn.execute(f"""INSERT INTO {value_table}({owner_column},field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (aggregate_uid, definition["uid"], *encoded))
            if definition["historized"]:
                conn.execute(f"""INSERT INTO {history_table}({owner_column},field_definition_uid,changed_by,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (aggregate_uid, definition["uid"], actor_id, *encoded))

    def _typed_value(self, conn, definition, value):
        kind = FieldType(definition["field_type"])
        if value is None:
            if definition["required"]: raise ContainerError("container.field.required", fields=[definition["field_key"]])
            return (None,) * 9
        if kind in {FieldType.STRING, FieldType.MULTILINE_TEXT}:
            if not isinstance(value, str): raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
            return (value, None, None, None, None, None, None, None, None)
        if kind is FieldType.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int): raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
            return (None, value, None, None, None, None, None, None, None)
        if kind is FieldType.DECIMAL:
            try: decimal = str(Decimal(str(value)))
            except (InvalidOperation, ValueError): raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
            return (None, None, decimal, None, None, None, None, None, None)
        if kind is FieldType.BOOLEAN:
            if not isinstance(value, bool): raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
            return (None, None, None, int(value), None, None, None, None, None)
        if kind is FieldType.DATE:
            try: parsed = value.isoformat() if isinstance(value, date) else date.fromisoformat(str(value)).isoformat()
            except ValueError: raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
            return (None, None, None, None, parsed, None, None, None, None)
        if kind is FieldType.DATETIME:
            try: parsed = value.isoformat() if isinstance(value, datetime) else datetime.fromisoformat(str(value)).isoformat()
            except ValueError: raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
            return (None, None, None, None, None, parsed, None, None, None)
        if kind in {FieldType.SINGLE_SELECT, FieldType.MULTI_SELECT}:
            selected = (value,) if kind is FieldType.SINGLE_SELECT else tuple(value) if not isinstance(value, str) else ()
            permitted = {r[0] for r in conn.execute("SELECT option_value FROM field_options WHERE field_definition_uid=?", (definition["uid"],))}
            if not selected or not set(selected) <= permitted: raise ContainerError("container.field.invalid_option", field=definition["field_key"])
            return ("\x1f".join(sorted(selected)), None, None, None, None, None, None, None, None)
        if not isinstance(value, str) or not value.strip(): raise ContainerError("container.field.invalid_type", field=definition["field_key"], expected=kind.value)
        if kind is FieldType.OBJECT_REFERENCE and not conn.execute("SELECT 1 FROM objects WHERE uid=?", (value,)).fetchone(): raise ContainerError("container.field.reference_not_found", field=definition["field_key"])
        if kind is FieldType.ARTIFACT_REFERENCE and not conn.execute("SELECT 1 FROM artifacts WHERE uid=?", (value,)).fetchone(): raise ContainerError("container.field.reference_not_found", field=definition["field_key"])
        if kind is FieldType.USER_REFERENCE:
            return (None, None, None, None, None, None, value, None, None)
        if kind is FieldType.OBJECT_REFERENCE:
            return (None, None, None, None, None, None, None, value, None)
        return (None, None, None, None, None, None, None, None, value)

    def _validate_draft(self, draft):
        if not draft.name.strip() or draft.version_number < 1 or not draft.create_roles:
            raise ContainerError("container.template.invalid_definition")
        if any(not isinstance(role, str) for role in draft.create_roles):
            raise ContainerError("container.template.invalid_roles")
        normalized_roles = [role.strip().upper() for role in draft.create_roles]
        if any(not role for role in normalized_roles) or len(normalized_roles) != len(set(normalized_roles)):
            raise ContainerError("container.template.invalid_roles")
        keys = [f.key for f in draft.fields]
        if any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)) or any(not key.strip() for key in keys): raise ContainerError("container.template.duplicate_field")
        for definition in draft.fields:
            if any(not isinstance(option, str) for option in definition.options) or len(definition.options) != len(set(definition.options)) or any(not option.strip() for option in definition.options):
                raise ContainerError("container.template.invalid_field_options", field=definition.key)
            if definition.options and definition.field_type not in {FieldType.SINGLE_SELECT, FieldType.MULTI_SELECT}:
                raise ContainerError("container.template.options_for_non_select", field=definition.key)
        if draft.kind is TemplateKind.ARTIFACT and draft.children: raise ContainerError("container.template.artifact_children_forbidden")
        child_keys = [c.key for c in draft.children]
        if any(not isinstance(key, str) for key in child_keys) or len(child_keys) != len(set(child_keys)) or any(not key.strip() for key in child_keys) or any(c.min_count < 0 or (c.max_count is not None and c.max_count < c.min_count) for c in draft.children): raise ContainerError("container.template.invalid_child")
        state_codes = [state.code for state in draft.lifecycle_states]
        if state_codes and (any(not isinstance(code, str) or not code.strip() for code in state_codes) or len(state_codes) != len(set(state_codes)) or sum(state.initial for state in draft.lifecycle_states) != 1 or draft.initial_state not in state_codes):
            raise ContainerError("container.template.invalid_lifecycle")
        transition_pairs = [(transition.from_state, transition.to_state) for transition in draft.lifecycle_transitions]
        if len(transition_pairs) != len(set(transition_pairs)):
            raise ContainerError("container.template.invalid_lifecycle")
        if any(transition.from_state not in state_codes or transition.to_state not in state_codes for transition in draft.lifecycle_transitions):
            raise ContainerError("container.template.invalid_lifecycle")

    @staticmethod
    def _blueprint_template_draft(
        template: BlueprintTemplateDraft,
        version_uids: dict[str, str],
    ) -> TemplateDraft:
        return TemplateDraft(
            kind=template.kind,
            name=template.name,
            version_number=1,
            create_roles=template.create_roles,
            fields=template.fields,
            children=tuple(
                ChildDefinition(
                    key=child.key,
                    template_version_uid=version_uids.get(child.template_key, child.template_key),
                    min_count=child.min_count,
                    max_count=child.max_count,
                    auto_create=child.auto_create,
                    mode=child.mode,
                )
                for child in template.children
            ),
            initial_state=template.initial_state,
            lifecycle_states=template.lifecycle_states,
            lifecycle_transitions=template.lifecycle_transitions,
        )

    def _insert_template_header(self, conn, actor_id, draft, template_uid, version_uid):
        if draft.template_uid is None:
            conn.execute(
                "INSERT INTO templates(uid,kind,name,created_by) VALUES(?,?,?,?)",
                (template_uid, draft.kind.value, draft.name, actor_id),
            )
        else:
            found = conn.execute("SELECT kind FROM templates WHERE uid=?", (template_uid,)).fetchone()
            if found is None or found["kind"] != draft.kind.value:
                raise ContainerError("container.template.not_found", template_uid=template_uid)
        existing = conn.execute(
            "SELECT 1 FROM template_versions WHERE template_uid=? AND version_number=?",
            (template_uid, draft.version_number),
        ).fetchone()
        if existing:
            raise ContainerError(
                "container.template.version_exists",
                template_uid=template_uid,
                version=draft.version_number,
            )
        conn.execute(
            "INSERT INTO template_versions(uid,template_uid,kind,name,version_number,state,initial_state,created_by) VALUES(?,?,?,?,?,?,?,?)",
            (
                version_uid,
                template_uid,
                draft.kind.value,
                draft.name,
                draft.version_number,
                TemplateState.DRAFT.value,
                draft.initial_state,
                actor_id,
            ),
        )

    def _insert_template_components(self, conn, draft, version_uid):
        for role in draft.create_roles:
            conn.execute(
                "INSERT INTO template_create_roles(template_version_uid,role_code) VALUES(?,?)",
                (version_uid, role.strip().upper()),
            )
        for position, definition in enumerate(draft.fields):
            field_uid = self._uid()
            conn.execute(
                "INSERT INTO field_definitions(uid,template_version_uid,field_key,field_type,required,searchable,linkable,printable,relevant_for_review,historized,editable,visible,position) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    field_uid,
                    version_uid,
                    definition.key,
                    definition.field_type.value,
                    int(definition.required),
                    int(definition.searchable),
                    int(definition.linkable),
                    int(definition.printable),
                    int(definition.relevant_for_review),
                    int(definition.historized),
                    int(definition.editable),
                    int(definition.visible),
                    position,
                ),
            )
            for option_position, option in enumerate(definition.options):
                conn.execute(
                    "INSERT INTO field_options(field_definition_uid,option_value,position) VALUES(?,?,?)",
                    (field_uid, option, option_position),
                )
        for position, child in enumerate(draft.children):
            child_template = conn.execute(
                "SELECT kind FROM template_versions WHERE uid=?",
                (child.template_version_uid,),
            ).fetchone()
            if child_template is None or child_template["kind"] != TemplateKind.OBJECT.value:
                raise ContainerError(
                    "container.template.child_template_not_found",
                    child_template_version_uid=child.template_version_uid,
                )
            conn.execute(
                "INSERT INTO child_definitions(template_version_uid,child_key,child_template_version_uid,min_count,max_count,auto_create,mode,position) VALUES(?,?,?,?,?,?,?,?)",
                (
                    version_uid,
                    child.key,
                    child.template_version_uid,
                    child.min_count,
                    child.max_count,
                    int(child.auto_create),
                    child.mode.value,
                    position,
                ),
            )
        states = draft.lifecycle_states or (LifecycleStateDefinition(draft.initial_state, initial=True),)
        for state in states:
            conn.execute(
                "INSERT INTO lifecycle_states(uid,template_version_uid,state_code,is_initial) VALUES(?,?,?,?)",
                (self._uid(), version_uid, state.code, int(state.initial)),
            )
        for transition in draft.lifecycle_transitions:
            transition_uid = self._uid()
            conn.execute(
                "INSERT INTO lifecycle_transitions(uid,template_version_uid,from_state_code,to_state_code,reason_required,signature_required) VALUES(?,?,?,?,?,?)",
                (
                    transition_uid,
                    version_uid,
                    transition.from_state,
                    transition.to_state,
                    int(transition.reason_required),
                    int(transition.signature_required),
                ),
            )
            for role in transition.allowed_roles:
                conn.execute(
                    "INSERT INTO lifecycle_transition_roles(transition_uid,role_code) VALUES(?,?)",
                    (transition_uid, role.strip().upper()),
                )

    def _get_module_blueprint(self, blueprint_uid: str) -> PublishedModuleBlueprint:
        with self._repository.read() as conn:
            row = conn.execute("SELECT * FROM module_blueprints WHERE uid=?", (blueprint_uid,)).fetchone()
            if row is None:
                raise ContainerError("container.blueprint.not_found", blueprint_uid=blueprint_uid)
            templates = conn.execute(
                "SELECT m.template_key,m.template_version_uid,m.is_root,v.kind,v.name FROM module_blueprint_templates m JOIN template_versions v ON v.uid=m.template_version_uid WHERE m.module_blueprint_uid=? ORDER BY m.template_key",
                (blueprint_uid,),
            ).fetchall()
        return PublishedModuleBlueprint(
            uid=row["uid"],
            blueprint_key=row["blueprint_key"],
            name=row["name"],
            description=row["description"],
            root_template_version_uid=row["root_template_version_uid"],
            templates=tuple(
                PublishedBlueprintTemplate(
                    template_key=template["template_key"],
                    template_version_uid=template["template_version_uid"],
                    kind=TemplateKind(template["kind"]),
                    name=template["name"],
                    is_root=bool(template["is_root"]),
                )
                for template in templates
            ),
            published_by=row["published_by"],
        )

    def _runtime_template_definition(self, conn, context, row) -> RuntimeTemplateDefinition:
        """Build a published template projection without leaking role policy to clients."""
        template_version_uid = row["template_version_uid"]
        field_rows = conn.execute(
            """SELECT * FROM field_definitions
               WHERE template_version_uid=? AND visible=1
               ORDER BY position,field_key""",
            (template_version_uid,),
        ).fetchall()
        fields = tuple(
            FieldDefinition(
                key=field["field_key"],
                field_type=FieldType(field["field_type"]),
                required=bool(field["required"]),
                searchable=bool(field["searchable"]),
                linkable=bool(field["linkable"]),
                printable=bool(field["printable"]),
                relevant_for_review=bool(field["relevant_for_review"]),
                historized=bool(field["historized"]),
                editable=bool(field["editable"]),
                visible=True,
                options=tuple(
                    option["option_value"]
                    for option in conn.execute(
                        """SELECT option_value FROM field_options
                           WHERE field_definition_uid=? ORDER BY position,option_value""",
                        (field["uid"],),
                    ).fetchall()
                ),
            )
            for field in field_rows
        )
        children = tuple(
            ChildDefinition(
                key=child["child_key"],
                template_version_uid=child["child_template_version_uid"],
                min_count=child["min_count"],
                max_count=child["max_count"],
                auto_create=bool(child["auto_create"]),
                mode=ChildMode(child["mode"]),
            )
            for child in self._children(conn, template_version_uid)
        )
        states = tuple(
            LifecycleStateDefinition(state["state_code"], bool(state["is_initial"]))
            for state in conn.execute(
                """SELECT state_code,is_initial FROM lifecycle_states
                   WHERE template_version_uid=? ORDER BY state_code""",
                (template_version_uid,),
            ).fetchall()
        )
        transitions: list[RuntimeTransitionDefinition] = []
        transition_rows = conn.execute(
            """SELECT * FROM lifecycle_transitions
               WHERE template_version_uid=? ORDER BY from_state_code,to_state_code""",
            (template_version_uid,),
        ).fetchall()
        for transition in transition_rows:
            allowed_roles = {
                role["role_code"]
                for role in conn.execute(
                    """SELECT role_code FROM lifecycle_transition_roles
                       WHERE transition_uid=?""",
                    (transition["uid"],),
                ).fetchall()
            }
            if allowed_roles and not self._actor_allowed(context, allowed_roles):
                continue
            transitions.append(
                RuntimeTransitionDefinition(
                    from_state=transition["from_state_code"],
                    to_state=transition["to_state_code"],
                    reason_required=bool(transition["reason_required"]),
                    signature_required=bool(transition["signature_required"]),
                )
            )
        create_roles = {
            role["role_code"]
            for role in conn.execute(
                """SELECT role_code FROM template_create_roles
                   WHERE template_version_uid=?""",
                (template_version_uid,),
            ).fetchall()
        }
        has_hidden_required_field = conn.execute(
            """SELECT 1 FROM field_definitions
               WHERE template_version_uid=? AND required=1 AND visible=0 LIMIT 1""",
            (template_version_uid,),
        ).fetchone() is not None
        return RuntimeTemplateDefinition(
            template_key=row["template_key"],
            template_version_uid=template_version_uid,
            kind=TemplateKind(row["kind"]),
            name=row["name"],
            fields=fields,
            children=children,
            lifecycle_states=states,
            lifecycle_transitions=tuple(transitions),
            create_allowed=(
                self._actor_allowed(context, create_roles)
                and not has_hidden_required_field
            ),
            is_root=bool(row["is_root"]),
        )

    def _assert_publishable(self, conn, uid):
        for child in self._children(conn, uid):
            row = conn.execute("SELECT state,kind FROM template_versions WHERE uid=?", (child["child_template_version_uid"],)).fetchone()
            if row is None or row["state"] != TemplateState.PUBLISHED.value or row["kind"] != TemplateKind.OBJECT.value:
                raise ContainerError("container.template.inconsistent_publish", child_key=child["child_key"])

    def _published_object_template(self, conn, uid):
        row = conn.execute("SELECT * FROM template_versions WHERE uid=?", (uid,)).fetchone()
        if row is None or row["kind"] != TemplateKind.OBJECT.value or row["state"] != TemplateState.PUBLISHED.value:
            raise ContainerError("container.template.not_published", template_version_uid=uid)
        return row

    def _published_artifact_template(self, conn, uid):
        row = conn.execute("SELECT * FROM template_versions WHERE uid=?", (uid,)).fetchone()
        if row is None or row["kind"] != TemplateKind.ARTIFACT.value or row["state"] != TemplateState.PUBLISHED.value:
            raise ContainerError("container.template.not_published", template_version_uid=uid)
        return row

    def _mutable_artifact(self, conn, artifact_uid, expected_revision):
        row = conn.execute("SELECT * FROM artifacts WHERE uid=?", (artifact_uid,)).fetchone()
        if row is None:
            raise ContainerError("container.artifact.not_found", artifact_uid=artifact_uid)
        if row["immutable"]:
            raise ContainerError("container.artifact.immutable", artifact_uid=artifact_uid)
        if row["archived"] or self._object_is_archived(conn, row["owner_object_uid"]):
            raise ContainerError("container.archive.read_only", artifact_uid=artifact_uid)
        if row["revision"] != expected_revision:
            raise ContainerError("container.revision.conflict", expected=expected_revision, actual=row["revision"])
        return row

    @staticmethod
    def _artifact_file_from_row(row):
        return ArtifactFile(row["uid"], row["artifact_uid"], row["original_name"], row["media_type"], row["size_bytes"], row["content_hash"], bool(row["immutable"]))

    @staticmethod
    def _object_from_row(row):
        return ContainerObject(row["uid"], row["template_version_uid"], StructuralParentRef(ParentKind(row["parent_kind"]), row["parent_uid"]), row["depth"], row["revision"], row["state"], bool(row["fixed"]), bool(row["archived"]))

    @staticmethod
    def _artifact_from_row(row):
        return Artifact(row["uid"], row["template_version_uid"], row["owner_object_uid"], row["state"], row["revision"], bool(row["immutable"]), row["final_snapshot_uid"], bool(row["archived"]))

    def _aggregate_row(self, conn, kind, uid):
        table = "objects" if kind is ReferenceKind.OBJECT else "artifacts"
        return conn.execute(f"SELECT * FROM {table} WHERE uid=?", (uid,)).fetchone()

    def _object_is_archived(self, conn, object_uid):
        current = object_uid
        while current:
            row = conn.execute("SELECT parent_kind,parent_uid,archived FROM objects WHERE uid=?", (current,)).fetchone()
            if row is None: return False
            if row["archived"]: return True
            current = row["parent_uid"] if row["parent_kind"] == ParentKind.OBJECT.value else None
        return False

    def _decision(self, conn, context, action, kind, uid, row=None):
        row = row or self._aggregate_row(conn, kind, uid)
        if row is None: return ActionDecision(False, "container.authorization.not_found")
        if action is ActionCode.PHYSICAL_DELETE:
            if kind is not ReferenceKind.OBJECT:
                return ActionDecision(False, "container.deletion.object_only")
            return self._deletion_decision(conn, context, row)
        if self._actor_allowed(context, {"ADMIN", "QMB"}) or row["created_by"] == context.user_id:
            privileged = True
        else:
            role_values = tuple(context.global_roles) or ("",)
            placeholders = ",".join("?" * len(role_values))
            sql = "SELECT permission_code FROM acl_entries WHERE aggregate_kind=? AND aggregate_uid=? AND (subject_user_id=? OR subject_role_code IN (%s))" % placeholders
            permissions = {r[0] for r in conn.execute(sql, (kind.value, uid, context.user_id, *role_values))}
            privileged = action.value in permissions or "ALL" in permissions
            if action in {ActionCode.VIEW, ActionCode.SEARCH} and "VIEW" in permissions: privileged = True
        if not privileged: return ActionDecision(False, "container.authorization.denied")
        archived = bool(row["archived"]) if "archived" in row.keys() else False
        if kind is ReferenceKind.ARTIFACT and self._object_is_archived(conn, row["owner_object_uid"]): archived = True
        if action is ActionCode.ARCHIVE and archived:
            return ActionDecision(False, "container.archive.already_archived")
        if action is ActionCode.REACTIVATE and not archived:
            return ActionDecision(False, "container.archive.not_archived")
        if action not in {ActionCode.VIEW, ActionCode.SEARCH, ActionCode.REACTIVATE} and archived:
            return ActionDecision(False, "container.archive.read_only")
        if action in {ActionCode.UPDATE, ActionCode.FINALIZE, ActionCode.REFERENCE} and kind is ReferenceKind.ARTIFACT and row["immutable"]:
            return ActionDecision(False, "container.artifact.immutable")
        if action is ActionCode.MOVE and kind is ReferenceKind.OBJECT and row["fixed"]:
            return ActionDecision(False, "container.tree.fixed_child")
        return ActionDecision(True)

    def _require_action(self, conn, context, action, kind, uid, row=None):
        decision = self._decision(conn, context, action, kind, uid, row)
        if not decision.allowed: raise ContainerError(decision.denial_code or "container.authorization.denied", **decision.params)

    def _ensure_correction_link_type(self, conn, actor_id):
        row = conn.execute("SELECT * FROM link_types WHERE code='corrects'").fetchone()
        if row is None:
            uid = self._uid()
            conn.execute("INSERT INTO link_types(uid,code,source_kind,target_kind,inverse_label) VALUES(?,?,?,?,?)", (uid, "corrects", ReferenceKind.ARTIFACT.value, ReferenceKind.ARTIFACT.value, "corrected_by"))
            self._audit(conn, "link_type.created", uid, actor_id)
            row = conn.execute("SELECT * FROM link_types WHERE uid=?", (uid,)).fetchone()
        return row

    def _object_snapshot_hash(self, conn, obj):
        rows = conn.execute("SELECT d.field_key,d.field_type,v.string_value,v.integer_value,v.decimal_value,v.boolean_value,v.date_value,v.datetime_value,v.user_uid,v.object_uid_value,v.artifact_uid_value FROM object_field_values v JOIN field_definitions d ON d.uid=v.field_definition_uid WHERE v.object_uid=? ORDER BY d.field_key", (obj["uid"],)).fetchall()
        references = conn.execute(
            "SELECT uid,source_kind,source_uid,target_kind,target_uid,link_type_uid FROM references_table WHERE (source_kind='OBJECT' AND source_uid=?) OR (target_kind='OBJECT' AND target_uid=?) ORDER BY uid",
            (obj["uid"], obj["uid"]),
        ).fetchall()
        payload = {
            "object": {
                "uid": obj["uid"],
                "state": obj["state"],
                "template": obj["template_version_uid"],
                "revision": obj["revision"],
                "parent_kind": obj["parent_kind"],
                "parent_uid": obj["parent_uid"],
                "depth": obj["depth"],
            },
            "fields": [dict(row) for row in rows],
            "references": [dict(row) for row in references],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

    def _create_object_signature(self, conn, context, obj, meaning):
        snapshot_uid, signature_uid = self._uid(), self._uid()
        state_hash = self._object_snapshot_hash(conn, obj)
        conn.execute("INSERT INTO object_snapshots(uid,object_uid,state_hash,template_version_uid,object_state,object_revision,parent_kind,parent_uid,depth) VALUES(?,?,?,?,?,?,?,?,?)", (snapshot_uid, obj["uid"], state_hash, obj["template_version_uid"], obj["state"], obj["revision"], obj["parent_kind"], obj["parent_uid"], obj["depth"]))
        conn.execute("INSERT INTO object_snapshot_field_values(snapshot_uid,field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value) SELECT ?,field_definition_uid,string_value,integer_value,decimal_value,boolean_value,date_value,datetime_value,user_uid,object_uid_value,artifact_uid_value FROM object_field_values WHERE object_uid=?", (snapshot_uid, obj["uid"]))
        conn.execute("INSERT INTO object_snapshot_references(snapshot_uid,reference_uid,source_kind,source_uid,target_kind,target_uid,link_type_uid) SELECT ?,uid,source_kind,source_uid,target_kind,target_uid,link_type_uid FROM references_table WHERE (source_kind='OBJECT' AND source_uid=?) OR (target_kind='OBJECT' AND target_uid=?)", (snapshot_uid, obj["uid"], obj["uid"]))
        conn.execute("INSERT INTO signatures(uid,object_uid,snapshot_uid,state_hash,signer_user_id,meaning) VALUES(?,?,?,?,?,?)", (signature_uid, obj["uid"], snapshot_uid, state_hash, context.user_id, meaning.strip()))
        return ObjectSignature(signature_uid, obj["uid"], snapshot_uid, state_hash, context.user_id, meaning.strip())

    def _set_archive(self, actor, object_uid, *, expected_revision, archived):
        context = self._actor(actor)
        with self._repository.transaction() as conn:
            obj = self._aggregate_row(conn, ReferenceKind.OBJECT, object_uid)
            if obj is None: raise ContainerError("container.object.not_found", object_uid=object_uid)
            self._require_action(conn, context, ActionCode.ARCHIVE if archived else ActionCode.REACTIVATE, ReferenceKind.OBJECT, object_uid, obj)
            if obj["revision"] != expected_revision: raise ContainerError("container.revision.conflict", expected=expected_revision, actual=obj["revision"])
            rows = conn.execute("WITH RECURSIVE t(uid) AS (SELECT uid FROM objects WHERE uid=? UNION ALL SELECT o.uid FROM objects o JOIN t ON o.parent_kind='OBJECT' AND o.parent_uid=t.uid) SELECT uid FROM t", (object_uid,)).fetchall()
            ids = tuple(r[0] for r in rows)
            marks = ",".join("?" * len(ids))
            conn.execute(f"UPDATE objects SET archived=?,archived_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,archived_by=CASE WHEN ? THEN ? ELSE NULL END,revision=revision+1 WHERE uid IN ({marks})", (int(archived), int(archived), int(archived), context.user_id, *ids))
            conn.execute(f"UPDATE artifacts SET archived=? WHERE owner_object_uid IN ({marks})", (int(archived), *ids))
            self._audit(conn, "object.archived" if archived else "object.reactivated", object_uid, context.user_id)
        self._publish("domain.container.object.archived.v1" if archived else "domain.container.object.reactivated.v1", object_uid, context)
        return self.get_object(context, object_uid)

    def _snapshot_hash(self, conn, artifact, files):
        fields = []
        query = """SELECT d.field_key,d.field_type,v.string_value,v.integer_value,v.decimal_value,v.boolean_value,v.date_value,v.datetime_value,v.user_uid,v.object_uid_value,v.artifact_uid_value
                   FROM artifact_field_values v JOIN field_definitions d ON d.uid=v.field_definition_uid
                   WHERE v.artifact_uid=? ORDER BY d.field_key"""
        for row in conn.execute(query, (artifact["uid"],)):
            fields.append(dict(row))
        references = [dict(row) for row in conn.execute("SELECT uid,source_kind,source_uid,target_kind,target_uid,link_type_uid FROM references_table WHERE source_uid=? OR target_uid=? ORDER BY uid", (artifact["uid"], artifact["uid"]))]
        payload = {
            "artifact": {"uid": artifact["uid"], "template_version_uid": artifact["template_version_uid"], "owner_object_uid": artifact["owner_object_uid"], "state": artifact["state"]},
            "fields": fields,
            "files": [{"uid": row["uid"], "original_name": row["original_name"], "media_type": row["media_type"], "size_bytes": row["size_bytes"], "content_hash": row["content_hash"]} for row in files],
            "references": references,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _storage(self) -> ArtifactFileStorage:
        if self._artifact_storage is None:
            raise ContainerError("container.storage.unavailable")
        return self._artifact_storage

    @staticmethod
    def _decoded_value(row):
        field_type = FieldType(row["field_type"])
        if field_type in {FieldType.STRING, FieldType.MULTILINE_TEXT, FieldType.SINGLE_SELECT, FieldType.MULTI_SELECT}:
            return row["string_value"]
        if field_type is FieldType.INTEGER:
            return row["integer_value"]
        if field_type is FieldType.DECIMAL:
            return Decimal(row["decimal_value"]) if row["decimal_value"] is not None else None
        if field_type is FieldType.BOOLEAN:
            return bool(row["boolean_value"]) if row["boolean_value"] is not None else None
        if field_type is FieldType.DATE:
            return date.fromisoformat(row["date_value"]) if row["date_value"] else None
        if field_type is FieldType.DATETIME:
            return datetime.fromisoformat(row["datetime_value"]) if row["datetime_value"] else None
        if field_type is FieldType.USER_REFERENCE:
            return row["user_uid"]
        if field_type is FieldType.OBJECT_REFERENCE:
            return row["object_uid_value"]
        return row["artifact_uid_value"]

    def _read_visible_values(self, conn, aggregate_kind: str, uid: str) -> dict[str, object]:
        table = "object_field_values" if aggregate_kind == "object" else "artifact_field_values"
        owner = "object_uid" if aggregate_kind == "object" else "artifact_uid"
        rows = conn.execute(
            f"SELECT d.field_key,d.field_type,v.string_value,v.integer_value,v.decimal_value,v.boolean_value,v.date_value,v.datetime_value,v.user_uid,v.object_uid_value,v.artifact_uid_value FROM {table} v JOIN field_definitions d ON d.uid=v.field_definition_uid WHERE v.{owner}=? AND d.visible=1 ORDER BY d.field_key",
            (uid,),
        ).fetchall()
        return {row["field_key"]: self._decoded_value(row) for row in rows}

    @staticmethod
    def _safe_original_name(original_name: str) -> str:
        if not original_name or Path(original_name).name != original_name or "/" in original_name or "\\" in original_name or any(ord(char) < 32 or ord(char) == 127 for char in original_name):
            raise ContainerError("container.storage.invalid_original_name")
        return original_name

    @staticmethod
    def _safe_media_type(media_type: str) -> str:
        if not media_type.strip() or "\r" in media_type or "\n" in media_type:
            raise ContainerError("container.storage.invalid_media_type")
        return media_type.strip()

    def _parent_depth(self, conn, parent):
        if parent.kind is ParentKind.WORKSPACE_ROOT:
            if not conn.execute("SELECT 1 FROM workspace_roots WHERE uid=?", (parent.uid,)).fetchone(): raise ContainerError("container.tree.parent_not_found", parent_uid=parent.uid)
            return 0
        row = conn.execute("SELECT depth FROM objects WHERE uid=?", (parent.uid,)).fetchone()
        if row is None: raise ContainerError("container.tree.parent_not_found", parent_uid=parent.uid)
        return row["depth"]

    def _assert_child_cardinality(self, conn, parent, child_template_uid, excluding_uid=None):
        if parent.kind is not ParentKind.OBJECT: return
        row = conn.execute("SELECT template_version_uid FROM objects WHERE uid=?", (parent.uid,)).fetchone()
        if row is None: raise ContainerError("container.tree.parent_not_found", parent_uid=parent.uid)
        rule = conn.execute("SELECT max_count FROM child_definitions WHERE template_version_uid=? AND child_template_version_uid=?", (row["template_version_uid"], child_template_uid)).fetchone()
        if rule is None: return
        if rule["max_count"] is not None:
            query = "SELECT COUNT(*) FROM objects WHERE parent_kind='OBJECT' AND parent_uid=? AND template_version_uid=?" + (" AND uid<>?" if excluding_uid else "")
            args = (parent.uid, child_template_uid, excluding_uid) if excluding_uid else (parent.uid, child_template_uid)
            if conn.execute(query, args).fetchone()[0] >= rule["max_count"]: raise ContainerError("container.tree.cardinality")

    def _children(self, conn, uid): return conn.execute("SELECT * FROM child_definitions WHERE template_version_uid=? ORDER BY position", (uid,)).fetchall()
    def _is_descendant(self, conn, candidate, ancestor):
        current = candidate
        while True:
            row = conn.execute("SELECT parent_kind,parent_uid FROM objects WHERE uid=?", (current,)).fetchone()
            if row is None or row["parent_kind"] == ParentKind.WORKSPACE_ROOT.value: return False
            if row["parent_uid"] == ancestor: return True
            current = row["parent_uid"]
    def _subtree_height(self, conn, uid):
        base = conn.execute("SELECT depth FROM objects WHERE uid=?", (uid,)).fetchone()["depth"]
        rows = conn.execute("WITH RECURSIVE t(uid,depth) AS (SELECT uid,depth FROM objects WHERE uid=? UNION ALL SELECT o.uid,o.depth FROM objects o JOIN t ON o.parent_kind='OBJECT' AND o.parent_uid=t.uid) SELECT MAX(depth) FROM t", (uid,)).fetchone()
        return rows[0] - base
    def _shift_descendant_depths(self, conn, uid, delta):
        conn.execute("WITH RECURSIVE t(uid) AS (SELECT uid FROM objects WHERE parent_kind='OBJECT' AND parent_uid=? UNION ALL SELECT o.uid FROM objects o JOIN t ON o.parent_kind='OBJECT' AND o.parent_uid=t.uid) UPDATE objects SET depth=depth+? WHERE uid IN (SELECT uid FROM t)", (uid, delta))
    def _audit(self, conn, event_type, aggregate_uid, actor_user_id, details=None):
        audit_uid = self._uid()
        conn.execute("INSERT INTO audit_events(uid,event_type,aggregate_uid,actor_user_id) VALUES(?,?,?,?)", (audit_uid, event_type, aggregate_uid, actor_user_id))
        for key, value in sorted((details or {}).items()):
            conn.execute("INSERT INTO audit_event_details(audit_event_uid,detail_key,detail_value) VALUES(?,?,?)", (audit_uid, str(key), str(value)))
        return audit_uid
    def _actor(self, actor):
        try: return require_confirmed_user_context(actor)
        except Exception as exc: raise ContainerError("container.authorization.confirmed_actor_required") from exc
    def _require_template_admin(self, context):
        if not self._actor_allowed(context, {"ADMIN", "QMB"}): raise ContainerError("container.authorization.template_denied")
    def _require_deletion_governance_actor(self, context):
        if not self._actor_allowed(context, {"ADMIN", "QMB"}): raise ContainerError("container.deletion.governance_denied")
    @staticmethod
    def _actor_allowed(context, allowed): return bool({r.upper() for r in context.global_roles} & allowed) or ("QMB" in allowed and context.is_qmb)
    def _publish(self, name, aggregate_uid, context): self._event_bus.publish(EventEnvelope.create(name, "container", {"uid": aggregate_uid}, actor_user_id=context.user_id, correlation_id=context.request_id))
    @staticmethod
    def _uid(): return str(uuid4())
