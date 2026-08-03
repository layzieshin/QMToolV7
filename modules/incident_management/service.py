"""Incident management service facade."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import (
    action_ops,
    artifact_ops,
    assessment_ops,
    effectiveness_ops,
    grouping_ops,
    incident_ops,
    inquiry_ops,
    leadership_ops,
    management_review_ops,
    query_ops,
    report_ops,
    role_ops,
    capa_ops,
    root_cause_ops,
)
from .contracts import (
    ActionType,
    ArtifactType,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentListFilter,
    IncidentSubmission,
    ModuleInternalRole,
    SimilarIncidentQuery,
)


class IncidentManagementService:
    def __init__(
        self,
        *,
        repo: object,
        storage: object,
        event_bus: object | None = None,
        audit_logger: object | None = None,
        settings_service: object | None = None,
        usermanagement_service: object | None = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._event_bus = event_bus
        self._audit_logger = audit_logger
        self._settings_service = settings_service
        self._usermanagement = usermanagement_service

    def _user(self) -> object:
        if self._usermanagement is None:
            return None
        getter = getattr(self._usermanagement, "get_current_user", None)
        if not callable(getter):
            return None
        return getter()

    def _settings(self) -> dict:
        if self._settings_service is None:
            return {}
        getter = getattr(self._settings_service, "get_module_settings", None)
        if not callable(getter):
            return {}
        return dict(getter("incident_management"))

    def submit_incident(self, submission: IncidentSubmission) -> object:
        return incident_ops.submit_incident(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            submission=submission,
            settings=self._settings(),
        )

    def get_incident(self, incident_id: str) -> object:
        return incident_ops.get_incident(repo=self._repo, user=self._user(), incident_id=incident_id)

    def list_incidents(self, flt: IncidentListFilter | None = None) -> list:
        return incident_ops.list_incidents(repo=self._repo, user=self._user(), flt=flt)

    def open_inquiry(self, incident_id: str, question: str) -> object:
        return inquiry_ops.open_inquiry(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            question=question,
        )

    def answer_inquiry(self, incident_id: str, answer: str) -> object:
        return inquiry_ops.answer_inquiry(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            answer=answer,
        )

    def assess_incident(self, incident_id: str, assessment: IncidentAssessmentInput) -> object:
        return assessment_ops.assess_incident(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            settings=self._settings(),
            user=self._user(),
            incident_id=incident_id,
            assessment=assessment,
        )

    def list_my_incidents(self) -> list:
        return incident_ops.list_my_incidents(repo=self._repo, user=self._user())

    def list_incident_timeline(self, incident_id: str) -> list:
        return incident_ops.list_incident_timeline(
            repo=self._repo,
            user=self._user(),
            incident_id=incident_id,
        )

    def list_similar_incidents(self, query: SimilarIncidentQuery) -> list:
        return query_ops.list_similar_incidents(repo=self._repo, user=self._user(), query=query)

    def list_qmb_review_queue(self) -> list:
        return query_ops.list_qmb_review_queue(repo=self._repo, user=self._user())

    def list_open_inquiries(self) -> list:
        return query_ops.list_open_inquiries(repo=self._repo, user=self._user())

    def list_open_actions(self) -> list:
        return query_ops.list_open_actions(repo=self._repo, user=self._user())

    def list_pending_effectiveness_reviews(self) -> list:
        return query_ops.list_pending_effectiveness_reviews(repo=self._repo, user=self._user())

    def list_similar_incident_candidates(self, incident_id: str) -> list:
        return query_ops.list_similar_incident_candidates(
            repo=self._repo,
            user=self._user(),
            incident_id=incident_id,
        )

    def list_capa_relevant_incidents(self) -> list:
        return query_ops.list_capa_relevant_incidents(repo=self._repo, user=self._user())

    def create_action(
        self,
        incident_id: str,
        action_type: ActionType,
        description: str,
        owner_user_id: str | None = None,
        due_at: datetime | None = None,
    ) -> object:
        return action_ops.create_action(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            settings=self._settings(),
            user=self._user(),
            incident_id=incident_id,
            action_type=action_type,
            description=description,
            owner_user_id=owner_user_id,
            due_at=due_at,
        )

    def complete_action(self, action_id: str) -> object:
        return action_ops.complete_action(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            action_id=action_id,
        )

    def start_capa(
        self,
        incident_id: str,
        trigger_reason: str | None = None,
        goal: str | None = None,
        description: str | None = None,
    ) -> object:
        return capa_ops.start_capa(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            trigger_reason=trigger_reason,
            goal=goal,
            description=description,
        )

    def update_capa(
        self,
        incident_id: str,
        status: CapaStatus | None = None,
        goal: str | None = None,
        description: str | None = None,
    ) -> object:
        return capa_ops.update_capa(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            status=status,
            goal=goal,
            description=description,
        )

    def create_root_cause_analysis(self, incident_id: str, **fields: str | None) -> object:
        return root_cause_ops.create_root_cause_analysis(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            immediate_event=fields.get("immediate_event"),
            trigger=fields.get("trigger"),
            root_causes=fields.get("root_causes"),
            similar_prior=fields.get("similar_prior"),
            systemic_weakness=fields.get("systemic_weakness"),
            future_risk=fields.get("future_risk"),
            method=fields.get("method"),
        )

    def plan_effectiveness_review(
        self,
        incident_id: str,
        criteria: str,
        planned_at: datetime | None = None,
    ) -> object:
        return effectiveness_ops.plan_effectiveness_review(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            settings=self._settings(),
            user=self._user(),
            incident_id=incident_id,
            criteria=criteria,
            planned_at=planned_at,
        )

    def complete_effectiveness_review(
        self,
        incident_id: str,
        effective: bool,
        result: str,
        notes: str | None = None,
    ) -> object:
        return effectiveness_ops.complete_effectiveness_review(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            effective=effective,
            result=result,
            notes=notes,
        )

    def attach_artifact(
        self,
        incident_id: str,
        source_path: Path,
        artifact_type: ArtifactType = ArtifactType.ATTACHMENT,
        metadata: dict[str, str] | None = None,
    ) -> object:
        return artifact_ops.attach_artifact(
            repo=self._repo,
            storage=self._storage,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            source_path=source_path,
            artifact_type=artifact_type,
            metadata=metadata,
        )

    def generate_incident_report(self, incident_id: str) -> object:
        return report_ops.generate_incident_report(
            repo=self._repo,
            storage=self._storage,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            settings=self._settings(),
            user=self._user(),
            incident_id=incident_id,
        )

    def generate_register_pdf(self, output_path: Path | None = None) -> object:
        return report_ops.generate_register_pdf(
            repo=self._repo,
            storage=self._storage,
            settings=self._settings(),
            user=self._user(),
            output_path=output_path,
        )

    def generate_capa_report(self) -> object:
        return report_ops.generate_capa_report(repo=self._repo, user=self._user())

    def generate_patterns_report(self) -> object:
        return report_ops.generate_patterns_report(repo=self._repo, user=self._user())

    def create_incident_group(self, name: str, description: str | None = None) -> object:
        return grouping_ops.create_incident_group(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            name=name,
            description=description,
        )

    def link_incident_to_group(self, incident_id: str, group_id: str) -> object:
        return grouping_ops.link_incident_to_group(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            group_id=group_id,
        )

    def forward_to_leadership(self, incident_id: str, leadership_user_id: str) -> object:
        return leadership_ops.forward_to_leadership(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            leadership_user_id=leadership_user_id,
        )

    def acknowledge_leadership_review(self, incident_id: str, comment: str | None = None) -> object:
        return leadership_ops.acknowledge_leadership_review(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
            comment=comment,
        )

    def list_leadership_queue(self) -> list:
        return leadership_ops.list_leadership_queue(repo=self._repo, user=self._user())

    def create_management_review(self, period_start: datetime, period_end: datetime) -> object:
        return management_review_ops.create_management_review(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            period_start=period_start,
            period_end=period_end,
        )

    def mark_management_review_in_discussion(self, batch_id: str) -> object:
        return management_review_ops.mark_management_review_in_discussion(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            batch_id=batch_id,
        )

    def acknowledge_management_review_items(
        self,
        batch_id: str,
        incident_ids: list[str] | None = None,
    ) -> list:
        return management_review_ops.acknowledge_management_review_items(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            batch_id=batch_id,
            incident_ids=incident_ids,
        )

    def generate_management_review_report(self, batch_id: str) -> object:
        return report_ops.generate_management_review_report(
            repo=self._repo,
            storage=self._storage,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            settings=self._settings(),
            user=self._user(),
            batch_id=batch_id,
        )

    def close_incident(self, incident_id: str) -> object:
        result = effectiveness_ops.close_incident(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
        )
        report_ops.generate_incident_report(
            repo=self._repo,
            storage=self._storage,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            settings=self._settings(),
            user=self._user(),
            incident_id=incident_id,
        )
        return result

    def archive_incident(self, incident_id: str) -> object:
        return effectiveness_ops.archive_incident(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            incident_id=incident_id,
        )

    def assign_module_role(self, target_user_id: str, role_name: ModuleInternalRole) -> object:
        return role_ops.assign_module_role(
            repo=self._repo,
            event_bus=self._event_bus,
            audit_logger=self._audit_logger,
            user=self._user(),
            target_user_id=target_user_id,
            role_name=role_name,
        )

    def list_module_roles(self, role_name: ModuleInternalRole | None = None) -> list:
        return role_ops.list_module_roles(
            repo=self._repo,
            user=self._user(),
            role_name=role_name,
        )

    def get_module_settings(self) -> dict:
        return self._settings()

    def set_module_settings(
        self,
        values: dict,
        *,
        actor: object,
        acknowledge_governance_change: bool = False,
    ) -> dict:
        if self._settings_service is None:
            return {}
        setter = getattr(self._settings_service, "set_module_settings", None)
        if not callable(setter):
            return {}
        auth_user = self._user()
        from . import authorization as auth

        auth.require_admin_or_qmb(auth_user)
        setter(
            "incident_management",
            values,
            actor=actor,
            acknowledge_governance_change=acknowledge_governance_change,
        )
        return self._settings()
