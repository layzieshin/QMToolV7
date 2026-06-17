"""PDF report generation."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from . import authorization as auth
from . import artifact_ops
from . import eventing
from . import settings_rules
from .contracts import (
    ArtifactType,
    IncidentCase,
    ReportResult,
)
from .sqlite_repository import SQLiteIncidentRepository
from .storage import IncidentArtifactStorage


def _draw_lines(pdf, x: float, y: float, lines: list[str], *, line_height: float = 12) -> float:
    width, height = A4
    for line in lines:
        pdf.drawString(x, y, line[:120])
        y -= line_height
        if y < 60:
            pdf.showPage()
            y = height - 50
    return y


def _build_case_pdf(
    repo: SQLiteIncidentRepository,
    incident_id: str,
    *,
    report_template_id: str = "default",
) -> bytes:
    case = repo.get_incident(incident_id)
    timeline = repo.list_timeline(incident_id)
    actions = repo.list_actions(incident_id)
    capa = repo.get_capa(incident_id)
    rca = repo.get_rca(incident_id)
    effectiveness = repo.get_effectiveness_review(incident_id)
    leadership = repo.get_leadership_ack(incident_id)
    artifacts = repo.list_artifacts(incident_id)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, f"Fallakte: {case.incident_id}")
    y -= 16
    pdf.setFont("Helvetica", 9)
    pdf.drawString(50, y, f"Report template: {report_template_id}")
    y -= 20
    pdf.setFont("Helvetica", 10)
    header_lines = [
        f"Status: {case.status.value}",
        f"Titel: {case.title}",
        f"Kategorie: {case.category}",
        f"Gemeldet: {case.reported_at.isoformat()}",
        f"Melder: {case.reporter_user_id}",
        f"Bereich: {case.area or '-'}",
        f"Prozess: {case.process_name or '-'}",
        f"Geraet: {case.device or '-'}",
        f"Beschreibung: {case.description}",
    ]
    y = _draw_lines(pdf, 50, y, header_lines)

    if case.classification:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "QMB-Bewertung")
        y -= 16
        pdf.setFont("Helvetica", 10)
        assess_lines = [
            f"Einstufung: {case.classification.value}",
            f"Kritisch: {case.is_critical}",
            f"Kritikalitaetsgrund: {case.criticality_reason or '-'}",
            f"Wiederholt: {case.is_repeated}",
            f"CAPA erforderlich: {case.capa_required}",
            f"CAPA-Grund: {case.capa_reason or '-'}",
            f"RCA erforderlich: {case.root_cause_required}",
            f"Leitung erforderlich: {case.leadership_required}",
        ]
        y = _draw_lines(pdf, 50, y, assess_lines)

    if rca is not None:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Ursachenanalyse")
        y -= 16
        pdf.setFont("Helvetica", 10)
        rca_lines = [
            f"Sofortereignis: {rca.immediate_event or '-'}",
            f"Ausloeser: {rca.trigger or '-'}",
            f"Ursachen: {rca.root_causes or '-'}",
            f"Systemische Schwaeche: {rca.systemic_weakness or '-'}",
            f"Zukuenftiges Risiko: {rca.future_risk or '-'}",
            f"Methode: {rca.method or '-'}",
        ]
        y = _draw_lines(pdf, 50, y, rca_lines)

    if capa is not None:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "CAPA")
        y -= 16
        pdf.setFont("Helvetica", 10)
        capa_lines = [
            f"Status: {capa.status.value}",
            f"Ausloeser: {capa.trigger_reason or '-'}",
            f"Ziel: {capa.goal or '-'}",
            f"Beschreibung: {capa.description or '-'}",
        ]
        y = _draw_lines(pdf, 50, y, capa_lines)

    if actions:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Massnahmen")
        y -= 16
        pdf.setFont("Helvetica", 9)
        for action in actions:
            y = _draw_lines(
                pdf,
                50,
                y,
                [f"{action.action_type.value} | {action.status.value} | {action.description}"],
                line_height=11,
            )

    if effectiveness is not None:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Wirksamkeitspruefung")
        y -= 16
        pdf.setFont("Helvetica", 10)
        eff_lines = [
            f"Status: {effectiveness.status.value}",
            f"Kriterien: {effectiveness.criteria}",
            f"Ergebnis: {effectiveness.result or '-'}",
            f"Wirksam: {effectiveness.effective}",
            f"Notizen: {effectiveness.notes or '-'}",
        ]
        y = _draw_lines(pdf, 50, y, eff_lines)

    if leadership is not None:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Leitung")
        y -= 16
        pdf.setFont("Helvetica", 10)
        lead_lines = [
            f"Status: {leadership.status.value}",
            f"Leitung: {leadership.leadership_user_id}",
            f"Kommentar: {leadership.comment or '-'}",
        ]
        y = _draw_lines(pdf, 50, y, lead_lines)

    if artifacts:
        y -= 8
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "Artefakte")
        y -= 16
        pdf.setFont("Helvetica", 9)
        for artifact in artifacts:
            y = _draw_lines(
                pdf,
                50,
                y,
                [f"{artifact.artifact_type.value}: {artifact.original_filename}"],
                line_height=11,
            )

    y -= 8
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Timeline")
    y -= 16
    pdf.setFont("Helvetica", 9)
    timeline_lines = [f"{e.created_at.isoformat()} | {e.summary}" for e in timeline]
    _draw_lines(pdf, 50, y, timeline_lines[:60], line_height=11)
    pdf.save()
    return buffer.getvalue()


def generate_incident_report(
    *,
    repo: SQLiteIncidentRepository,
    storage: IncidentArtifactStorage,
    event_bus: object | None,
    audit_logger: object | None,
    settings: dict,
    user: object,
    incident_id: str,
) -> ReportResult:
    auth.require_authenticated(user)
    template_id = settings_rules.resolve_report_template_id(settings, "case")
    data = _build_case_pdf(repo, incident_id, report_template_id=template_id)
    filename = f"{incident_id}_report.pdf"
    artifact = artifact_ops.register_generated_artifact(
        repo=repo,
        storage=storage,
        incident_id=incident_id,
        filename=filename,
        data=data,
        artifact_type=ArtifactType.CASE_REPORT_PDF,
        actor_user_id=auth.user_id(user),
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.report.case",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.report.generated.v1",
        actor_user_id=auth.user_id(user),
        payload={
            "incident_id": incident_id,
            "report_type": "case",
            "report_template_id": template_id,
        },
    )
    return ReportResult(
        report_id=artifact.artifact_id,
        filename=filename,
        storage_key=artifact.storage_key,
        mime_type="application/pdf",
        size_bytes=artifact.size_bytes or 0,
        report_template_id=template_id,
    )


def generate_register_pdf(
    *,
    repo: SQLiteIncidentRepository,
    storage: IncidentArtifactStorage,
    settings: dict,
    user: object,
    output_path: Path | None = None,
) -> ReportResult:
    auth.require_authenticated(user)
    template_id = settings_rules.resolve_report_template_id(settings, "register")
    cases = repo.list_incidents()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Incident Register Export")
    y -= 16
    pdf.setFont("Helvetica", 9)
    pdf.drawString(50, y, f"Report template: {template_id}")
    y -= 20
    pdf.setFont("Helvetica", 9)
    for case in cases[:200]:
        line = f"{case.incident_id} | {case.status.value} | {case.title[:40]}"
        pdf.drawString(50, y, line)
        y -= 12
        if y < 60:
            pdf.showPage()
            y = height - 50
    pdf.save()
    data = buffer.getvalue()
    filename = "incident_register.pdf"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return ReportResult(
            report_id=eventing.new_id(),
            filename=filename,
            storage_key=None,
            mime_type="application/pdf",
            size_bytes=len(data),
            report_template_id=template_id,
        )
    stored = storage.write_bytes(
        incident_id="_register",
        artifact_type="register_export",
        filename=filename,
        data=data,
    )
    return ReportResult(
        report_id=eventing.new_id(),
        filename=filename,
        storage_key=stored.storage_key,
        mime_type="application/pdf",
        size_bytes=len(data),
        report_template_id=template_id,
    )


def generate_capa_report(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> ReportResult:
    auth.require_qmb(user)
    cases = [c for c in repo.list_incidents() if c.capa_required]
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "CAPA-Relevant Incidents")
    y -= 24
    pdf.setFont("Helvetica", 9)
    for case in cases[:200]:
        line = f"{case.incident_id} | {case.status.value} | {case.title[:40]}"
        pdf.drawString(50, y, line)
        y -= 12
        if y < 60:
            pdf.showPage()
            y = height - 50
    pdf.save()
    data = buffer.getvalue()
    return ReportResult(
        report_id=eventing.new_id(),
        filename="capa_incidents.pdf",
        storage_key=None,
        mime_type="application/pdf",
        size_bytes=len(data),
    )


def generate_patterns_report(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
) -> ReportResult:
    auth.require_qmb(user)
    cases = repo.list_incidents()
    repeated = [c for c in cases if c.is_repeated]
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Repeated / Pattern Incidents")
    y -= 24
    pdf.setFont("Helvetica", 9)
    for case in repeated[:200]:
        line = f"{case.incident_id} | {case.category} | {case.title[:40]}"
        pdf.drawString(50, y, line)
        y -= 12
        if y < 60:
            pdf.showPage()
            y = height - 50
    pdf.save()
    data = buffer.getvalue()
    return ReportResult(
        report_id=eventing.new_id(),
        filename="pattern_incidents.pdf",
        storage_key=None,
        mime_type="application/pdf",
        size_bytes=len(data),
    )


def generate_management_review_report(
    *,
    repo: SQLiteIncidentRepository,
    storage: IncidentArtifactStorage,
    event_bus: object | None,
    audit_logger: object | None,
    settings: dict,
    user: object,
    batch_id: str,
) -> ReportResult:
    auth.require_qmb(user)
    template_id = settings_rules.resolve_report_template_id(settings, "management_review")
    batch = repo.get_management_batch(batch_id)
    items = repo.list_management_items(batch_id)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, f"Management Review: {batch_id}")
    y -= 16
    pdf.setFont("Helvetica", 9)
    pdf.drawString(50, y, f"Report template: {template_id}")
    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Period: {batch.period_start.date()} - {batch.period_end.date()}")
    y -= 24
    pdf.setFont("Helvetica", 9)
    for item in items:
        case = repo.get_incident(item.incident_id)
        line = f"{case.incident_id} | {item.status.value} | {case.title[:35]}"
        pdf.drawString(50, y, line)
        y -= 12
        if y < 60:
            pdf.showPage()
            y = height - 50
    pdf.save()
    data = buffer.getvalue()
    filename = f"management_review_{batch_id}.pdf"
    stored = storage.write_bytes(
        incident_id=f"_mgmt_{batch_id}",
        artifact_type="management_review",
        filename=filename,
        data=data,
    )
    from dataclasses import replace

    repo.update_management_batch(replace(batch, report_storage_key=stored.storage_key))
    eventing.emit_audit(
        audit_logger,
        action="incident.management_review.report",
        actor=auth.user_id(user),
        target=batch_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.report.generated.v1",
        actor_user_id=auth.user_id(user),
        payload={
            "batch_id": batch_id,
            "report_type": "management_review",
            "report_template_id": template_id,
        },
    )
    return ReportResult(
        report_id=batch_id,
        filename=filename,
        storage_key=stored.storage_key,
        mime_type="application/pdf",
        size_bytes=len(data),
        report_template_id=template_id,
    )
