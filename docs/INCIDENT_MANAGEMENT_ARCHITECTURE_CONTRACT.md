# Incident Management Architecture Contract (VA-Aligned v1)

This contract defines the normative domain model for event, deviation, risk, and CAPA management.
It is the implementation baseline for compliance with the process instruction (VA).

Related guides:

- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/MODULE_INTEGRATION_POLICY.md`
- `docs/MODULES_USER_GUIDE.md`

## Module goal

`incident_management` is a **licensed core module** for systematic handling of:

- Events (Beobachtung, Fehler, Abweichung, Beinahe-Ereignis, Risiko)
- QMB assessment and inquiries
- Immediate, corrective, and preventive actions
- CAPA, root cause analysis, effectiveness review
- Leadership acknowledgement (critical/CAPA cases)
- Management review batches (periodic, by report date)
- Artifacts and PDF reports

CAPA, reports, and management review are **internal subdomains** — not separate runtime modules.

## Public boundary

External callers import only:

- `modules/incident_management/api.py`
- `modules/incident_management/contracts.py`

Port name: `incident_management_api`  
License tag: `incident_management`

## Confirmed architecture decisions

| Topic | Decision |
| --- | --- |
| Incident visibility | **All authenticated users may read any incident** (`list_incidents`, `get_incident`). Steering actions (assess, CAPA, close, settings, etc.) remain **service-side role checks** — adapters do not enforce business authorization. |
| Management review vs. closure | Two separate tracks. Leadership acknowledgement blocks closure only for critical/CAPA-required incidents. Management review is a periodic batch by report date for **all** incidents regardless of closure status. **Does not block closure.** |
| Management review status | **Not** part of `IncidentStatus`. `ManagementReviewItemStatus`: `included` → `in_discussion` → `acknowledged`. |
| Leitung (V1) | Module-internal role via `assign_module_role` / `module_role_assignments` in the incident DB — **not** a settings key. Service filters leadership queue and acknowledgements. PyQt shows views to all logged-in users; leadership content filtered by service (empty/denied without assignment). No shell custom-role logic. |
| QMB wizard | Hybrid without persisted draft. Inquiries separate; similar incidents via query; `assess_incident` atomic for classification decisions; CAPA/RCA/actions via separate use cases afterward. |

## Incident ID rule

Format: `YYYYMMDD_NNNN` (example: `20260616_0001`)

- Date = **report date** (`reported_at`), not discovery/assessment/closure date
- Sequence increments per report date
- Generated in `incident_numbering.py` (not CLI/GUI)

## IncidentStatus V1

```text
SUBMITTED
QMB_REVIEW
INQUIRY_OPEN
INQUIRY_ANSWERED
ASSESSED
DOCUMENTATION_ONLY
ROOT_CAUSE_REQUIRED
ROOT_CAUSE_IN_PROGRESS
CAPA_REQUIRED
CAPA_PLANNING
ACTIONS_IN_PROGRESS
FOLLOW_UP
EFFECTIVENESS_PLANNED
EFFECTIVENESS_REVIEW
CLOSURE_REVIEW
LEADERSHIP_ACK_REQUIRED
CLOSED
ARCHIVED
```

`DOCUMENTATION_ONLY`: observation path after assessment when no CAPA/RCA follow-up is required.

## ManagementReviewItemStatus (separate)

```text
included
in_discussion
acknowledged
```

## Core objects

| Object | Responsibility |
| --- | --- |
| `IncidentCase` | Central case file |
| `IncidentSubmission` | Adapter DTO for report preview (not persisted as draft) |
| `IncidentAssessment` | QMB classification outcome |
| `IncidentInquiry` | QMB inquiry and answer |
| `IncidentAction` | Immediate / corrective / preventive action |
| `IncidentCapa` | CAPA record |
| `RootCauseAnalysis` | Documented root cause analysis |
| `EffectivenessReview` | Planned and completed effectiveness check |
| `IncidentArtifact` | Attachments and generated case report PDF |
| `IncidentGroup` | Collective case / linked incidents |
| `LeadershipAcknowledgement` | Forward and acknowledge by Leitung |
| `ManagementReviewBatch` | Period batch by report date |
| `ManagementReviewReport` | PDF report for management review |
| `IncidentTimelineEntry` | Case history / audit trail |
| `ModuleRoleAssignment` | Module role `Leitung` |

## Submit required fields (V1)

| Field | Required |
| --- | --- |
| `title` | yes |
| `description` | yes |
| `category` | yes (from settings) |
| `reported_at` | yes (report date; defaults to now if omitted in adapter) |
| `area`, `process`, `device`, `labels` | optional |

## Roles

**Read visibility (product rule):** Every logged-in user may list and read all incidents. Per-case read is not restricted by reporter or role.

**Steering actions:** Enforced in the service layer (`authorization.py`) — adapters pass through API errors only.

| Role | Rights |
| --- | --- |
| `User` | Report incidents, read all incidents in register, answer own/adressed inquiries |
| `QMB` | Assess, inquire, manage CAPA/actions, forward to Leitung, close |
| `Admin` | Module settings and module role assignments |
| `Leitung` (module) | Read forwarded cases, comment, acknowledge |
| `QMB + Admin` | Assign `Leitung` module role via `assign_module_role` (DB `module_role_assignments`) |

## CAPA requirement (V1)

CAPA required when:

- Incident is critical, or
- Incident is repeated/multiple, or
- QMB manually enforces CAPA with documented reason

## Closure blockers

| Blocker | Applies when |
| --- | --- |
| Assessment incomplete | always |
| Open inquiry | always |
| RCA missing | CAPA-required path |
| Open CAPA/actions | CAPA-required path |
| Effectiveness not completed | CAPA-required path |
| Leadership not acknowledged | critical or CAPA-required |
| Management review | **never blocks closure** |

## Reports V1

| Report | Required | Stored as incident artifact |
| --- | --- | --- |
| Case PDF per incident | yes | yes (auto on generation) |
| Register export PDF | yes | no |
| CAPA-relevant view/report | yes | no |
| Pattern/recurrence view | yes | no |
| Management review PDF | yes | batch record only |

## Domain events

Pattern: `domain.incident_management.<event>.v1`

Publish **after** successful persistence. Payload small, versioned, non-sensitive. No separate notification subsystem.

`capa.required.v1` is emitted **only on assess** when `capa_required` becomes true — not again on `start_capa` / `update_capa` (`capa.updated.v1` only).

RCA creation event name: `incident.rca.created.v1` (not `root_cause.created`).

User-uploaded attachments emit `artifact.attached.v1`. Auto-generated case PDF emits `report.generated.v1` (and is stored as a case artifact; it does not also emit `artifact.attached.v1`).

### Workflow events (V1)

| Event | When |
| --- | --- |
| `incident.submitted.v1` | New incident persisted |
| `inquiry.opened.v1` | QMB opens inquiry |
| `inquiry.answered.v1` | Inquiry answered |
| `incident.assessed.v1` | QMB assessment persisted |
| `capa.required.v1` | Assess sets `capa_required` (once per case at assess) |
| `capa.updated.v1` | CAPA started or updated |
| `incident.rca.created.v1` | Root cause analysis created |
| `action.created.v1` | Action created |
| `action.completed.v1` | Action completed |
| `effectiveness.planned.v1` | Effectiveness review planned |
| `effectiveness.reviewed.v1` | Effectiveness review completed |
| `leadership.forwarded.v1` | Case forwarded to Leitung |
| `leadership.acknowledged.v1` | Leitung acknowledgement |
| `incident.grouped.v1` | Incident linked to group |
| `artifact.attached.v1` | User attachment stored |
| `report.generated.v1` | Case or management-review PDF generated |
| `incident.closed.v1` | Incident closed |
| `incident.archived.v1` | Incident archived |
| `management_review.created.v1` | Management review batch created |
| `management_review.in_discussion.v1` | Batch marked in discussion |
| `management_review.acknowledged.v1` | Batch items acknowledged |
| `role.assigned.v1` | Module role (Leitung) assigned |

### Lifecycle events

| Event | When |
| --- | --- |
| `module.started.v1` | Module started |
| `module.stopped.v1` | Module stopped |

Register, CAPA overview, and pattern/recurrence reports do **not** emit domain events (audit-only or ephemeral bytes where applicable).

## Settings V1

| Key | Governance |
| --- | --- |
| `incident_db_path`, `artifacts_root` | operational |
| `categories`, `label_groups` | operational |
| `criticality_groups`, `standard_deadlines`, `effectiveness_delay`, `capa_required_rules`, `report_templates` | governance_critical |

Leitung assignment is **not** a settings key. Use `assign_module_role` / `module_role_assignments` in the incident database.

## CLI-first delivery

CLI group `incident` must be green before PyQt contributions.

## Non-goals V1

- No cross-platform module role infrastructure in usermanagement
- No documents/SOP workflow linkage
- No persisted QMB assessment draft
- No runtime plugin loading
