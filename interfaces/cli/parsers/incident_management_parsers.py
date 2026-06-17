"""CLI parsers for incident_management."""
from __future__ import annotations

import argparse


def register_incident_management_parsers(sub: argparse._SubParsersAction) -> None:
    incident_parser = sub.add_parser("incident", help="Incident management operations")
    incident_sub = incident_parser.add_subparsers(dest="incident_command", required=True)

    submit = incident_sub.add_parser("submit", help="Submit a new incident")
    submit.add_argument("--title", required=True)
    submit.add_argument("--description", required=True)
    submit.add_argument("--category", required=True)
    submit.add_argument("--reported-at", default=None)
    submit.add_argument("--area", default=None)
    submit.add_argument("--process", default=None)
    submit.add_argument("--device", default=None)
    submit.add_argument("--labels", default="", help="Comma-separated labels")

    get_p = incident_sub.add_parser("get", help="Get incident by ID")
    get_p.add_argument("--incident-id", required=True)

    list_p = incident_sub.add_parser("list", help="List incidents")
    list_p.add_argument("--status", default=None)
    list_p.add_argument("--category", default=None)

    inquiry_open = incident_sub.add_parser("inquiry-open", help="Open QMB inquiry")
    inquiry_open.add_argument("--incident-id", required=True)
    inquiry_open.add_argument("--question", required=True)

    inquiry_answer = incident_sub.add_parser("inquiry-answer", help="Answer inquiry")
    inquiry_answer.add_argument("--incident-id", required=True)
    inquiry_answer.add_argument("--answer", required=True)

    assess = incident_sub.add_parser("assess", help="QMB assess incident")
    assess.add_argument("--incident-id", required=True)
    assess.add_argument("--classification", required=True, choices=["OBSERVATION", "ERROR", "DEVIATION"])
    assess.add_argument("--critical", action="store_true")
    assess.add_argument("--critical-reason", default=None)
    assess.add_argument("--repeated", action="store_true")
    assess.add_argument("--capa-required", action="store_true")
    assess.add_argument("--capa-reason", default=None)
    assess.add_argument("--root-cause-required", action="store_true")
    assess.add_argument("--group-id", default=None)

    group_create = incident_sub.add_parser("group-create", help="Create incident group")
    group_create.add_argument("--name", required=True)
    group_create.add_argument("--description", default=None)

    group_link = incident_sub.add_parser("group-link", help="Link incident to group")
    group_link.add_argument("--incident-id", required=True)
    group_link.add_argument("--group-id", required=True)

    action_create = incident_sub.add_parser("action-create", help="Create action")
    action_create.add_argument("--incident-id", required=True)
    action_create.add_argument("--action-type", required=True, choices=[t.value for t in __import__("modules.incident_management.contracts", fromlist=["ActionType"]).ActionType])
    action_create.add_argument("--description", required=True)
    action_create.add_argument("--owner-user-id", default=None)

    action_complete = incident_sub.add_parser("action-complete", help="Complete action")
    action_complete.add_argument("--action-id", required=True)

    capa_start = incident_sub.add_parser("capa-start", help="Start CAPA")
    capa_start.add_argument("--incident-id", required=True)
    capa_start.add_argument("--goal", default=None)
    capa_start.add_argument("--description", default=None)

    capa_update = incident_sub.add_parser("capa-update", help="Update CAPA")
    capa_update.add_argument("--incident-id", required=True)
    capa_update.add_argument("--status", default=None)
    capa_update.add_argument("--goal", default=None)
    capa_update.add_argument("--description", default=None)

    rca_create = incident_sub.add_parser("root-cause-create", help="Create root cause analysis")
    rca_create.add_argument("--incident-id", required=True)
    rca_create.add_argument("--root-causes", required=True)

    eff_plan = incident_sub.add_parser("effectiveness-plan", help="Plan effectiveness review")
    eff_plan.add_argument("--incident-id", required=True)
    eff_plan.add_argument("--criteria", required=True)

    eff_complete = incident_sub.add_parser("effectiveness-complete", help="Complete effectiveness review")
    eff_complete.add_argument("--incident-id", required=True)
    eff_complete.add_argument("--effective", action="store_true")
    eff_complete.add_argument("--result", required=True)
    eff_complete.add_argument("--notes", default=None)

    artifact_add = incident_sub.add_parser("artifact-add", help="Attach artifact")
    artifact_add.add_argument("--incident-id", required=True)
    artifact_add.add_argument("--path", required=True)

    leadership_forward = incident_sub.add_parser("leadership-forward", help="Forward to leadership")
    leadership_forward.add_argument("--incident-id", required=True)
    leadership_forward.add_argument("--leadership-user-id", required=True)

    leadership_ack = incident_sub.add_parser("leadership-ack", help="Leadership acknowledge")
    leadership_ack.add_argument("--incident-id", required=True)
    leadership_ack.add_argument("--comment", default=None)

    report_case = incident_sub.add_parser("report-case", help="Generate case PDF report")
    report_case.add_argument("--incident-id", required=True)

    incident_sub.add_parser("report-register-pdf", help="Generate register PDF")
    incident_sub.add_parser("report-capa", help="Generate CAPA report")
    incident_sub.add_parser("report-patterns", help="Generate patterns report")

    mr_create = incident_sub.add_parser("management-review-create", help="Create management review batch")
    mr_create.add_argument("--period-start", required=True)
    mr_create.add_argument("--period-end", required=True)

    mr_discuss = incident_sub.add_parser("management-review-in-discussion", help="Mark batch in discussion")
    mr_discuss.add_argument("--batch-id", required=True)

    mr_ack = incident_sub.add_parser("management-review-ack", help="Acknowledge management review items")
    mr_ack.add_argument("--batch-id", required=True)
    mr_ack.add_argument("--incident-ids", default="", help="Comma-separated; empty = all")

    mr_report = incident_sub.add_parser("management-review-report", help="Generate management review PDF")
    mr_report.add_argument("--batch-id", required=True)

    close_p = incident_sub.add_parser("close", help="Close incident")
    close_p.add_argument("--incident-id", required=True)

    archive_p = incident_sub.add_parser("archive", help="Archive incident")
    archive_p.add_argument("--incident-id", required=True)

    role_assign = incident_sub.add_parser("role-assign", help="Assign module role")
    role_assign.add_argument("--user-id", required=True)
    role_assign.add_argument("--role", required=True, choices=["Leitung"])

    role_list = incident_sub.add_parser("role-list", help="List module roles")
    role_list.add_argument("--role", default=None)

    settings_get = incident_sub.add_parser("settings-get", help="Get module settings")
    settings_set = incident_sub.add_parser("settings-set", help="Set module settings")
    settings_set.add_argument("--key", required=True)
    settings_set.add_argument("--value", required=True)
    settings_set.add_argument("--acknowledge-governance-change", action="store_true")

    similar = incident_sub.add_parser("similar-list", help="List similar incidents")
    similar.add_argument("--incident-id", default=None)
    similar.add_argument("--category", default=None)

    leadership_queue = incident_sub.add_parser("leadership-queue", help="List leadership queue")
    leadership_queue.add_argument("placeholder", nargs="?", default=None)
