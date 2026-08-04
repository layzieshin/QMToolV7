"""Public API facade for incident_management."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
from .service import IncidentManagementService


class IncidentManagementApi:
    """Public port surface — delegates to service only."""

    def __init__(self, service: IncidentManagementService) -> None:
        self._service = service

    def submit_incident(self, submission: IncidentSubmission):
        return self._service.submit_incident(submission)

    def get_incident(self, incident_id: str):
        return self._service.get_incident(incident_id)

    def list_incidents(self, flt: IncidentListFilter | None = None):
        return self._service.list_incidents(flt)

    def list_my_incidents(self):
        return self._service.list_my_incidents()

    def list_incident_timeline(self, incident_id: str):
        return self._service.list_incident_timeline(incident_id)

    def open_inquiry(self, incident_id: str, question: str):
        return self._service.open_inquiry(incident_id, question)

    def answer_inquiry(self, incident_id: str, answer: str):
        return self._service.answer_inquiry(incident_id, answer)

    def assess_incident(self, incident_id: str, assessment: IncidentAssessmentInput):
        return self._service.assess_incident(incident_id, assessment)

    def list_similar_incidents(self, query: SimilarIncidentQuery):
        return self._service.list_similar_incidents(query)

    def list_qmb_review_queue(self):
        return self._service.list_qmb_review_queue()

    def list_open_inquiries(self):
        return self._service.list_open_inquiries()

    def list_open_actions(self):
        return self._service.list_open_actions()

    def list_pending_effectiveness_reviews(self):
        return self._service.list_pending_effectiveness_reviews()

    def list_similar_incident_candidates(self, incident_id: str):
        return self._service.list_similar_incident_candidates(incident_id)

    def list_capa_relevant_incidents(self):
        return self._service.list_capa_relevant_incidents()

    def create_action(
        self,
        incident_id: str,
        action_type: ActionType,
        description: str,
        owner_user_id: str | None = None,
        due_at: datetime | None = None,
    ):
        return self._service.create_action(
            incident_id,
            action_type,
            description,
            owner_user_id=owner_user_id,
            due_at=due_at,
        )

    def complete_action(self, action_id: str):
        return self._service.complete_action(action_id)

    def start_capa(
        self,
        incident_id: str,
        trigger_reason: str | None = None,
        goal: str | None = None,
        description: str | None = None,
    ):
        return self._service.start_capa(
            incident_id,
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
    ):
        return self._service.update_capa(incident_id, status=status, goal=goal, description=description)

    def create_root_cause_analysis(self, incident_id: str, **fields: str | None):
        return self._service.create_root_cause_analysis(incident_id, **fields)

    def plan_effectiveness_review(
        self,
        incident_id: str,
        criteria: str,
        planned_at: datetime | None = None,
    ):
        return self._service.plan_effectiveness_review(incident_id, criteria, planned_at=planned_at)

    def complete_effectiveness_review(
        self,
        incident_id: str,
        effective: bool,
        result: str,
        notes: str | None = None,
    ):
        return self._service.complete_effectiveness_review(incident_id, effective, result, notes=notes)

    def attach_artifact(
        self,
        incident_id: str,
        source_path: Path,
        artifact_type: ArtifactType = ArtifactType.ATTACHMENT,
        metadata: dict[str, str] | None = None,
    ):
        return self._service.attach_artifact(incident_id, source_path, artifact_type, metadata)

    def generate_incident_report(self, incident_id: str):
        return self._service.generate_incident_report(incident_id)

    def generate_register_pdf(self, output_path: Path | None = None):
        return self._service.generate_register_pdf(output_path)

    def generate_capa_report(self):
        return self._service.generate_capa_report()

    def generate_patterns_report(self):
        return self._service.generate_patterns_report()

    def create_incident_group(self, name: str, description: str | None = None):
        return self._service.create_incident_group(name, description)

    def link_incident_to_group(self, incident_id: str, group_id: str):
        return self._service.link_incident_to_group(incident_id, group_id)

    def forward_to_leadership(self, incident_id: str, leadership_user_id: str):
        return self._service.forward_to_leadership(incident_id, leadership_user_id)

    def acknowledge_leadership_review(self, incident_id: str, comment: str | None = None):
        return self._service.acknowledge_leadership_review(incident_id, comment)

    def list_leadership_queue(self):
        return self._service.list_leadership_queue()

    def create_management_review(self, period_start: datetime, period_end: datetime):
        return self._service.create_management_review(period_start, period_end)

    def mark_management_review_in_discussion(self, batch_id: str):
        return self._service.mark_management_review_in_discussion(batch_id)

    def acknowledge_management_review_items(self, batch_id: str, incident_ids: list[str] | None = None):
        return self._service.acknowledge_management_review_items(batch_id, incident_ids)

    def generate_management_review_report(self, batch_id: str):
        return self._service.generate_management_review_report(batch_id)

    def close_incident(self, incident_id: str):
        return self._service.close_incident(incident_id)

    def archive_incident(self, incident_id: str):
        return self._service.archive_incident(incident_id)

    def assign_module_role(self, target_user_id: str, role_name: ModuleInternalRole):
        return self._service.assign_module_role(target_user_id, role_name)

    def list_module_roles(self, role_name: ModuleInternalRole | None = None):
        return self._service.list_module_roles(role_name)

    def get_module_settings(self) -> dict:
        return self._service.get_module_settings()

    def set_module_settings(
        self,
        values: dict,
        *,
        actor: object,
        acknowledge_governance_change: bool = False,
    ) -> dict:
        """Persist module settings (J02 contract change).

        ``actor`` is required: a confirmed ``UserContext`` from ``issue_user_context`` /
        ``resolve_session``, or an explicit system/migration actor string. Bucket-C keys
        remain read-only via the settings service.
        """
        return self._service.set_module_settings(
            values,
            actor=actor,
            acknowledge_governance_change=acknowledge_governance_change,
        )
