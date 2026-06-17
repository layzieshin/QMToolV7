"""CLI commands for incident_management."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from modules.incident_management.contracts import (
    ActionType,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentListFilter,
    IncidentStatus,
    IncidentSubmission,
    ModuleInternalRole,
    SimilarIncidentQuery,
)
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def _case_dict(case) -> dict:
    return {
        "incident_id": case.incident_id,
        "status": case.status.value,
        "reporter_user_id": case.reporter_user_id,
        "reported_at": case.reported_at.isoformat(),
        "title": case.title,
        "description": case.description,
        "category": case.category,
        "labels": list(case.labels),
        "classification": case.classification.value if case.classification else None,
        "is_critical": case.is_critical,
        "capa_required": case.capa_required,
        "leadership_required": case.leadership_required,
    }


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=UTC)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def cmd_incident(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    usermanagement = container.get_port("usermanagement_service")
    api = container.get_port("incident_management_api")
    current_user = usermanagement.get_current_user()
    if current_user is None:
        print("BLOCKED: login required for incident commands")
        return 6

    try:
        cmd = args.incident_command
        if cmd == "submit":
            labels = tuple(x.strip() for x in args.labels.split(",") if x.strip())
            case = api.submit_incident(
                IncidentSubmission(
                    title=args.title,
                    description=args.description,
                    category=args.category,
                    reported_at=_parse_dt(args.reported_at),
                    labels=labels,
                    area=args.area,
                    process_name=args.process,
                    device=args.device,
                )
            )
            print(json.dumps(_case_dict(case), ensure_ascii=True))
            return 0
        if cmd == "get":
            case = api.get_incident(args.incident_id)
            print(json.dumps(_case_dict(case), ensure_ascii=True))
            return 0
        if cmd == "list":
            flt = IncidentListFilter(
                status=IncidentStatus(args.status) if args.status else None,
                category=args.category,
            )
            rows = api.list_incidents(flt)
            print(json.dumps([_case_dict(r) for r in rows], ensure_ascii=True))
            return 0
        if cmd == "inquiry-open":
            inquiry = api.open_inquiry(args.incident_id, args.question)
            print(json.dumps({"inquiry_id": inquiry.inquiry_id, "status": inquiry.status.value}, ensure_ascii=True))
            return 0
        if cmd == "inquiry-answer":
            inquiry = api.answer_inquiry(args.incident_id, args.answer)
            print(json.dumps({"inquiry_id": inquiry.inquiry_id, "status": inquiry.status.value}, ensure_ascii=True))
            return 0
        if cmd == "assess":
            case = api.assess_incident(
                args.incident_id,
                IncidentAssessmentInput(
                    classification=IncidentClassification(args.classification),
                    is_critical=bool(args.critical),
                    criticality_reason=args.critical_reason,
                    is_repeated=bool(args.repeated),
                    capa_required=bool(args.capa_required),
                    capa_reason=args.capa_reason,
                    root_cause_required=bool(args.root_cause_required),
                    group_id=args.group_id,
                ),
            )
            print(json.dumps(_case_dict(case), ensure_ascii=True))
            return 0
        if cmd == "group-create":
            group = api.create_incident_group(args.name, args.description)
            print(json.dumps({"group_id": group.group_id, "name": group.name}, ensure_ascii=True))
            return 0
        if cmd == "group-link":
            case = api.link_incident_to_group(args.incident_id, args.group_id)
            print(json.dumps(_case_dict(case), ensure_ascii=True))
            return 0
        if cmd == "action-create":
            action = api.create_action(
                args.incident_id,
                ActionType(args.action_type),
                args.description,
                owner_user_id=args.owner_user_id,
            )
            print(json.dumps({"action_id": action.action_id, "status": action.status.value}, ensure_ascii=True))
            return 0
        if cmd == "action-complete":
            action = api.complete_action(args.action_id)
            print(json.dumps({"action_id": action.action_id, "status": action.status.value}, ensure_ascii=True))
            return 0
        if cmd == "capa-start":
            capa = api.start_capa(args.incident_id, goal=args.goal, description=args.description)
            print(json.dumps({"capa_id": capa.capa_id, "status": capa.status.value}, ensure_ascii=True))
            return 0
        if cmd == "capa-update":
            capa = api.update_capa(
                args.incident_id,
                status=CapaStatus(args.status) if args.status else None,
                goal=args.goal,
                description=args.description,
            )
            print(json.dumps({"capa_id": capa.capa_id, "status": capa.status.value}, ensure_ascii=True))
            return 0
        if cmd == "root-cause-create":
            rca = api.create_root_cause_analysis(args.incident_id, root_causes=args.root_causes)
            print(json.dumps({"rca_id": rca.rca_id}, ensure_ascii=True))
            return 0
        if cmd == "effectiveness-plan":
            review = api.plan_effectiveness_review(args.incident_id, args.criteria)
            print(json.dumps({"review_id": review.review_id, "planned_at": review.planned_at.isoformat()}, ensure_ascii=True))
            return 0
        if cmd == "effectiveness-complete":
            review = api.complete_effectiveness_review(
                args.incident_id,
                effective=bool(args.effective),
                result=args.result,
                notes=args.notes,
            )
            print(json.dumps({"review_id": review.review_id, "effective": review.effective}, ensure_ascii=True))
            return 0
        if cmd == "artifact-add":
            artifact = api.attach_artifact(args.incident_id, Path(args.path))
            print(json.dumps({"artifact_id": artifact.artifact_id}, ensure_ascii=True))
            return 0
        if cmd == "leadership-forward":
            ack = api.forward_to_leadership(args.incident_id, args.leadership_user_id)
            print(json.dumps({"ack_id": ack.ack_id, "status": ack.status.value}, ensure_ascii=True))
            return 0
        if cmd == "leadership-ack":
            ack = api.acknowledge_leadership_review(args.incident_id, args.comment)
            print(json.dumps({"ack_id": ack.ack_id, "status": ack.status.value}, ensure_ascii=True))
            return 0
        if cmd == "leadership-queue":
            rows = api.list_leadership_queue()
            print(
                json.dumps(
                    [{"ack_id": r.ack_id, "incident_id": r.incident_id, "status": r.status.value} for r in rows],
                    ensure_ascii=True,
                )
            )
            return 0
        if cmd == "report-case":
            report = api.generate_incident_report(args.incident_id)
            print(json.dumps({"report_id": report.report_id, "filename": report.filename}, ensure_ascii=True))
            return 0
        if cmd == "report-register-pdf":
            report = api.generate_register_pdf()
            print(json.dumps({"report_id": report.report_id, "filename": report.filename}, ensure_ascii=True))
            return 0
        if cmd == "report-capa":
            report = api.generate_capa_report()
            print(json.dumps({"report_id": report.report_id, "filename": report.filename}, ensure_ascii=True))
            return 0
        if cmd == "report-patterns":
            report = api.generate_patterns_report()
            print(json.dumps({"report_id": report.report_id, "filename": report.filename}, ensure_ascii=True))
            return 0
        if cmd == "management-review-create":
            batch = api.create_management_review(_parse_dt(args.period_start), _parse_dt(args.period_end))
            print(json.dumps({"batch_id": batch.batch_id, "status": batch.status.value}, ensure_ascii=True))
            return 0
        if cmd == "management-review-in-discussion":
            batch = api.mark_management_review_in_discussion(args.batch_id)
            print(json.dumps({"batch_id": batch.batch_id, "status": batch.status.value}, ensure_ascii=True))
            return 0
        if cmd == "management-review-ack":
            ids = [x.strip() for x in args.incident_ids.split(",") if x.strip()] or None
            items = api.acknowledge_management_review_items(args.batch_id, ids)
            print(json.dumps([{"item_id": i.item_id, "status": i.status.value} for i in items], ensure_ascii=True))
            return 0
        if cmd == "management-review-report":
            report = api.generate_management_review_report(args.batch_id)
            print(json.dumps({"report_id": report.report_id, "filename": report.filename}, ensure_ascii=True))
            return 0
        if cmd == "close":
            case = api.close_incident(args.incident_id)
            print(json.dumps(_case_dict(case), ensure_ascii=True))
            return 0
        if cmd == "archive":
            case = api.archive_incident(args.incident_id)
            print(json.dumps(_case_dict(case), ensure_ascii=True))
            return 0
        if cmd == "role-assign":
            assignment = api.assign_module_role(args.user_id, ModuleInternalRole(args.role))
            print(json.dumps({"assignment_id": assignment.assignment_id, "user_id": assignment.user_id}, ensure_ascii=True))
            return 0
        if cmd == "role-list":
            role = ModuleInternalRole(args.role) if args.role else None
            rows = api.list_module_roles(role)
            print(
                json.dumps(
                    [{"user_id": r.user_id, "role_name": r.role_name.value} for r in rows],
                    ensure_ascii=True,
                )
            )
            return 0
        if cmd == "settings-get":
            print(json.dumps(api.get_module_settings(), ensure_ascii=True))
            return 0
        if cmd == "settings-set":
            settings = api.set_module_settings(
                {args.key: args.value},
                acknowledge_governance_change=bool(args.acknowledge_governance_change),
            )
            print(json.dumps(settings, ensure_ascii=True))
            return 0
        if cmd == "similar-list":
            rows = api.list_similar_incidents(
                SimilarIncidentQuery(incident_id=args.incident_id, category=args.category)
            )
            print(json.dumps([_case_dict(r) for r in rows], ensure_ascii=True))
            return 0
        print("FAILED: unknown incident command")
        return 7
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7


if __name__ == "__main__":
    raise SystemExit(0)
