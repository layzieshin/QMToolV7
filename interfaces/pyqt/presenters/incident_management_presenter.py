"""Incident management presenter – formatting and view-model helpers only."""
from __future__ import annotations

from datetime import datetime

from modules.incident_management.contracts import (
    EffectivenessReview,
    IncidentAction,
    IncidentCase,
    IncidentClassification,
    IncidentInquiry,
    LeadershipAcknowledgement,
    ReportResult,
)


class IncidentManagementPresenter:
    CLASSIFICATION_LABELS: dict[IncidentClassification, str] = {
        IncidentClassification.OBSERVATION: "Beobachtung",
        IncidentClassification.ERROR: "Fehler",
        IncidentClassification.DEVIATION: "Abweichung",
        IncidentClassification.NEAR_MISS: "Beinahe-Ereignis",
        IncidentClassification.RISK: "Risiko",
    }

    ACTION_TYPE_LABELS = {
        "IMMEDIATE_ACTION": "Sofortmassnahme",
        "CORRECTIVE_ACTION": "Korrekturmassnahme",
        "PREVENTIVE_ACTION": "Vorbeugemassnahme",
    }

    @staticmethod
    def format_datetime(value: datetime | None) -> str:
        if value is None:
            return "-"
        return value.astimezone().strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def format_optional_bool(value: bool | None) -> str:
        if value is None:
            return "-"
        return "Ja" if value else "Nein"

    @staticmethod
    def classification_label(value: IncidentClassification | None) -> str:
        if value is None:
            return "-"
        return IncidentManagementPresenter.CLASSIFICATION_LABELS.get(value, value.value)

    @staticmethod
    def format_case_row(case: IncidentCase) -> tuple[str, str, str, str, str]:
        return (
            case.incident_id,
            case.title,
            case.category,
            case.status.value,
            IncidentManagementPresenter.classification_label(case.classification),
        )

    @staticmethod
    def format_case_flags(case: IncidentCase) -> tuple[str, str]:
        return (
            IncidentManagementPresenter.format_optional_bool(case.capa_required),
            IncidentManagementPresenter.format_optional_bool(case.is_critical),
        )

    @staticmethod
    def format_incident_detail(case: IncidentCase) -> str:
        lines = [
            f"ID: {case.incident_id}",
            f"Titel: {case.title}",
            f"Status: {case.status.value}",
            f"Kategorie: {case.category}",
            f"Gemeldet: {IncidentManagementPresenter.format_datetime(case.reported_at)}",
            f"Melder: {case.reporter_user_id}",
            f"Einstufung: {IncidentManagementPresenter.classification_label(case.classification)}",
            f"Kritisch: {IncidentManagementPresenter.format_optional_bool(case.is_critical)}",
            f"CAPA: {IncidentManagementPresenter.format_optional_bool(case.capa_required)}",
            f"Labels: {', '.join(case.labels) if case.labels else '-'}",
            f"Bereich: {case.area or '-'}",
            f"Prozess: {case.process_name or '-'}",
            f"Geraet: {case.device or '-'}",
            "",
            case.description,
        ]
        return "\n".join(lines)

    @staticmethod
    def format_inquiry_row(inquiry: IncidentInquiry) -> tuple[str, str, str, str]:
        return (
            inquiry.incident_id,
            inquiry.inquiry_id,
            inquiry.question[:80],
            inquiry.status.value,
        )

    @staticmethod
    def format_action_row(action: IncidentAction) -> tuple[str, str, str, str, str]:
        action_type = IncidentManagementPresenter.ACTION_TYPE_LABELS.get(
            action.action_type.value,
            action.action_type.value,
        )
        return (
            action.incident_id,
            action.action_id,
            action_type,
            action.status.value,
            IncidentManagementPresenter.format_datetime(action.due_at),
        )

    @staticmethod
    def format_effectiveness_row(review: EffectivenessReview) -> tuple[str, str, str, str]:
        return (
            review.incident_id,
            review.review_id,
            review.status.value,
            IncidentManagementPresenter.format_datetime(review.planned_at),
        )

    @staticmethod
    def format_leadership_row(ack: LeadershipAcknowledgement) -> tuple[str, str, str, str]:
        return (
            ack.incident_id,
            ack.leadership_user_id,
            ack.status.value,
            IncidentManagementPresenter.format_datetime(ack.forwarded_at),
        )

    @staticmethod
    def format_report_result(result: ReportResult) -> str:
        return (
            f"Bericht: {result.filename}\n"
            f"Speicher: {result.storage_key or '-'}\n"
            f"Typ: {result.mime_type}, Groesse: {result.size_bytes} Bytes"
        )

    @staticmethod
    def preview_submission(
        *,
        title: str,
        description: str,
        category: str,
        reported_at: datetime,
        labels: tuple[str, ...],
        area: str | None,
        process_name: str | None,
        device: str | None,
        attachment_name: str | None,
    ) -> str:
        lines = [
            "Vorschau der Meldung",
            f"Titel: {title.strip()}",
            f"Kategorie: {category.strip()}",
            f"Feststellung: {IncidentManagementPresenter.format_datetime(reported_at)}",
            f"Labels: {', '.join(labels) if labels else '-'}",
            f"Bereich: {area or '-'}",
            f"Prozess: {process_name or '-'}",
            f"Geraet: {device or '-'}",
            f"Anhang: {attachment_name or '-'}",
            "",
            description.strip(),
        ]
        return "\n".join(lines)

    @staticmethod
    def status_line(*, count: int, label: str) -> str:
        return f"{label}: {count} Eintraege"

    @staticmethod
    def parse_labels(text: str) -> tuple[str, ...]:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return tuple(parts)
