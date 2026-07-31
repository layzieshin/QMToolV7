"""SQLite persistence for incident_management."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .contracts import (
    ActionStatus,
    ActionType,
    ArtifactType,
    CapaStatus,
    EffectivenessReviewStatus,
    IncidentAction,
    IncidentArtifact,
    IncidentCapa,
    IncidentCase,
    IncidentClassification,
    IncidentGroup,
    IncidentInquiry,
    IncidentListFilter,
    IncidentStatus,
    IncidentTimelineEntry,
    InquiryStatus,
    LeadershipAckStatus,
    LeadershipAcknowledgement,
    ManagementReviewBatch,
    ManagementReviewBatchStatus,
    ManagementReviewItem,
    ManagementReviewItemStatus,
    ModuleInternalRole,
    ModuleRoleAssignment,
    NotFoundError,
    RootCauseAnalysis,
    SimilarIncidentQuery,
    TimelineEntryType,
    EffectivenessReview,
)
from .incident_numbering import format_incident_id, report_date_key
from .validation import parse_iso_datetime


def _dt_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _dt_parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return parse_iso_datetime(value)


def _labels_load(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    data = json.loads(raw)
    return tuple(str(x) for x in data)


def _labels_dump(labels: tuple[str, ...]) -> str:
    return json.dumps(list(labels), ensure_ascii=True)


class SQLiteIncidentRepository:
    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def allocate_incident_id(self, reported_at: datetime) -> str:
        key = report_date_key(reported_at)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT next_seq FROM incident_id_counters WHERE report_date = ?",
                (key,),
            ).fetchone()
            if row is None:
                seq = 1
                conn.execute(
                    "INSERT INTO incident_id_counters (report_date, next_seq) VALUES (?, ?)",
                    (key, 2),
                )
            else:
                seq = int(row["next_seq"])
                conn.execute(
                    "UPDATE incident_id_counters SET next_seq = ? WHERE report_date = ?",
                    (seq + 1, key),
                )
            conn.commit()
        return format_incident_id(reported_at, seq)

    def _row_to_case(self, row: sqlite3.Row) -> IncidentCase:
        classification = row["classification"]
        return IncidentCase(
            incident_id=row["incident_id"],
            status=IncidentStatus(row["status"]),
            reporter_user_id=row["reporter_user_id"],
            reported_at=parse_iso_datetime(row["reported_at"]),
            title=row["title"],
            description=row["description"],
            category=row["category"],
            labels=_labels_load(row["labels_json"]),
            area=row["area"],
            process_name=row["process_name"],
            device=row["device"],
            classification=IncidentClassification(classification) if classification else None,
            is_critical=bool(row["is_critical"]) if row["is_critical"] is not None else None,
            criticality_reason=row["criticality_reason"],
            is_repeated=bool(row["is_repeated"]) if row["is_repeated"] is not None else None,
            capa_required=bool(row["capa_required"]) if row["capa_required"] is not None else None,
            capa_reason=row["capa_reason"],
            root_cause_required=bool(row["root_cause_required"]) if row["root_cause_required"] is not None else None,
            group_id=row["group_id"],
            leadership_required=bool(row["leadership_required"]),
            created_at=parse_iso_datetime(row["created_at"]),
            updated_at=parse_iso_datetime(row["updated_at"]),
            closed_at=_dt_parse(row["closed_at"]),
            archived_at=_dt_parse(row["archived_at"]),
        )

    def insert_incident(self, case: IncidentCase) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    incident_id, status, reporter_user_id, reported_at, title, description,
                    category, labels_json, area, process_name, device, classification,
                    is_critical, criticality_reason, is_repeated, capa_required, capa_reason,
                    root_cause_required, group_id, leadership_required, created_at, updated_at,
                    closed_at, archived_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case.incident_id,
                    case.status.value,
                    case.reporter_user_id,
                    _dt_iso(case.reported_at),
                    case.title,
                    case.description,
                    case.category,
                    _labels_dump(case.labels),
                    case.area,
                    case.process_name,
                    case.device,
                    case.classification.value if case.classification else None,
                    int(case.is_critical) if case.is_critical is not None else None,
                    case.criticality_reason,
                    int(case.is_repeated) if case.is_repeated is not None else None,
                    int(case.capa_required) if case.capa_required is not None else None,
                    case.capa_reason,
                    int(case.root_cause_required) if case.root_cause_required is not None else None,
                    case.group_id,
                    int(case.leadership_required),
                    _dt_iso(case.created_at),
                    _dt_iso(case.updated_at),
                    _dt_iso(case.closed_at),
                    _dt_iso(case.archived_at),
                ),
            )
            conn.commit()

    def update_incident(self, case: IncidentCase) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE incidents SET
                    status = ?, classification = ?, is_critical = ?, criticality_reason = ?,
                    is_repeated = ?, capa_required = ?, capa_reason = ?, root_cause_required = ?,
                    group_id = ?, leadership_required = ?, updated_at = ?, closed_at = ?, archived_at = ?
                WHERE incident_id = ?
                """,
                (
                    case.status.value,
                    case.classification.value if case.classification else None,
                    int(case.is_critical) if case.is_critical is not None else None,
                    case.criticality_reason,
                    int(case.is_repeated) if case.is_repeated is not None else None,
                    int(case.capa_required) if case.capa_required is not None else None,
                    case.capa_reason,
                    int(case.root_cause_required) if case.root_cause_required is not None else None,
                    case.group_id,
                    int(case.leadership_required),
                    _dt_iso(case.updated_at),
                    _dt_iso(case.closed_at),
                    _dt_iso(case.archived_at),
                    case.incident_id,
                ),
            )
            conn.commit()

    def get_incident(self, incident_id: str) -> IncidentCase:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"incident not found: {incident_id}")
        return self._row_to_case(row)

    def list_incidents(self, flt: IncidentListFilter | None = None) -> list[IncidentCase]:
        clauses: list[str] = []
        params: list[object] = []
        if flt:
            if flt.status is not None:
                clauses.append("status = ?")
                params.append(flt.status.value)
            if flt.category:
                clauses.append("category = ?")
                params.append(flt.category)
            if flt.reporter_user_id:
                clauses.append("reporter_user_id = ?")
                params.append(flt.reporter_user_id)
            if flt.from_reported_at:
                clauses.append("reported_at >= ?")
                params.append(_dt_iso(flt.from_reported_at))
            if flt.to_reported_at:
                clauses.append("reported_at <= ?")
                params.append(_dt_iso(flt.to_reported_at))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM incidents {where} ORDER BY reported_at DESC, incident_id DESC",
                params,
            ).fetchall()
        return [self._row_to_case(r) for r in rows]

    def list_similar_incidents(self, query: SimilarIncidentQuery) -> list[IncidentCase]:
        clauses: list[str] = []
        params: list[object] = []
        if query.incident_id:
            clauses.append("incident_id != ?")
            params.append(query.incident_id)
        if query.category:
            clauses.append("category = ?")
            params.append(query.category)
        if query.area:
            clauses.append("area = ?")
            params.append(query.area)
        if query.process_name:
            clauses.append("process_name = ?")
            params.append(query.process_name)
        if query.device:
            clauses.append("device = ?")
            params.append(query.device)
        if query.from_reported_at:
            clauses.append("reported_at >= ?")
            params.append(_dt_iso(query.from_reported_at))
        if query.to_reported_at:
            clauses.append("reported_at <= ?")
            params.append(_dt_iso(query.to_reported_at))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(query.limit, 100))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM incidents {where} ORDER BY reported_at DESC LIMIT ?",
                [*params, limit * 5 if query.labels else limit],
            ).fetchall()
        cases = [self._row_to_case(r) for r in rows]
        if query.labels:
            wanted = set(query.labels)
            cases = [c for c in cases if wanted.intersection(c.labels)]
        return cases[:limit]

    def add_timeline_entry(self, entry: IncidentTimelineEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incident_timeline (
                    entry_id, incident_id, entry_type, actor_user_id, summary, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.incident_id,
                    entry.entry_type.value,
                    entry.actor_user_id,
                    entry.summary,
                    json.dumps(entry.details, ensure_ascii=True, sort_keys=True),
                    _dt_iso(entry.created_at),
                ),
            )
            conn.commit()

    def list_timeline(self, incident_id: str) -> list[IncidentTimelineEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_timeline WHERE incident_id = ? ORDER BY created_at ASC",
                (incident_id,),
            ).fetchall()
        result: list[IncidentTimelineEntry] = []
        for row in rows:
            result.append(
                IncidentTimelineEntry(
                    entry_id=row["entry_id"],
                    incident_id=row["incident_id"],
                    entry_type=TimelineEntryType(row["entry_type"]),
                    actor_user_id=row["actor_user_id"],
                    summary=row["summary"],
                    details=json.loads(row["details_json"] or "{}"),
                    created_at=parse_iso_datetime(row["created_at"]),
                )
            )
        return result

    def add_inquiry(self, inquiry: IncidentInquiry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incident_inquiries (
                    inquiry_id, incident_id, question, answer, asked_by_user_id,
                    answered_by_user_id, asked_at, answered_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inquiry.inquiry_id,
                    inquiry.incident_id,
                    inquiry.question,
                    inquiry.answer,
                    inquiry.asked_by_user_id,
                    inquiry.answered_by_user_id,
                    _dt_iso(inquiry.asked_at),
                    _dt_iso(inquiry.answered_at),
                    inquiry.status.value,
                ),
            )
            conn.commit()

    def update_inquiry(self, inquiry: IncidentInquiry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE incident_inquiries SET answer = ?, answered_by_user_id = ?,
                    answered_at = ?, status = ? WHERE inquiry_id = ?
                """,
                (
                    inquiry.answer,
                    inquiry.answered_by_user_id,
                    _dt_iso(inquiry.answered_at),
                    inquiry.status.value,
                    inquiry.inquiry_id,
                ),
            )
            conn.commit()

    def get_open_inquiry(self, incident_id: str) -> IncidentInquiry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM incident_inquiries WHERE incident_id = ? AND status = ? ORDER BY asked_at DESC LIMIT 1",
                (incident_id, InquiryStatus.OPEN.value),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_inquiry(row)

    def _row_to_inquiry(self, row: sqlite3.Row) -> IncidentInquiry:
        return IncidentInquiry(
            inquiry_id=row["inquiry_id"],
            incident_id=row["incident_id"],
            question=row["question"],
            answer=row["answer"],
            asked_by_user_id=row["asked_by_user_id"],
            answered_by_user_id=row["answered_by_user_id"],
            asked_at=parse_iso_datetime(row["asked_at"]),
            answered_at=_dt_parse(row["answered_at"]),
            status=InquiryStatus(row["status"]),
        )

    def list_open_inquiries(self) -> list[IncidentInquiry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_inquiries WHERE status = ? ORDER BY asked_at DESC",
                (InquiryStatus.OPEN.value,),
            ).fetchall()
        return [self._row_to_inquiry(r) for r in rows]

    def add_action(self, action: IncidentAction) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incident_actions (
                    action_id, incident_id, action_type, status, description,
                    owner_user_id, due_at, completed_at, completed_by_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.action_id,
                    action.incident_id,
                    action.action_type.value,
                    action.status.value,
                    action.description,
                    action.owner_user_id,
                    _dt_iso(action.due_at),
                    _dt_iso(action.completed_at),
                    action.completed_by_user_id,
                    _dt_iso(action.created_at),
                ),
            )
            conn.commit()

    def update_action(self, action: IncidentAction) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE incident_actions SET status = ?, completed_at = ?, completed_by_user_id = ?
                WHERE action_id = ?
                """,
                (
                    action.status.value,
                    _dt_iso(action.completed_at),
                    action.completed_by_user_id,
                    action.action_id,
                ),
            )
            conn.commit()

    def get_action(self, action_id: str) -> IncidentAction:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM incident_actions WHERE action_id = ?", (action_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"action not found: {action_id}")
        return self._row_to_action(row)

    def list_actions(self, incident_id: str) -> list[IncidentAction]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_actions WHERE incident_id = ? ORDER BY created_at ASC",
                (incident_id,),
            ).fetchall()
        return [self._row_to_action(r) for r in rows]

    def list_all_open_actions(self) -> list[IncidentAction]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_actions WHERE status != ? ORDER BY created_at DESC",
                (ActionStatus.COMPLETED.value,),
            ).fetchall()
        return [self._row_to_action(r) for r in rows]

    def _row_to_action(self, row: sqlite3.Row) -> IncidentAction:
        return IncidentAction(
            action_id=row["action_id"],
            incident_id=row["incident_id"],
            action_type=ActionType(row["action_type"]),
            status=ActionStatus(row["status"]),
            description=row["description"],
            owner_user_id=row["owner_user_id"],
            due_at=_dt_parse(row["due_at"]),
            completed_at=_dt_parse(row["completed_at"]),
            completed_by_user_id=row["completed_by_user_id"],
            created_at=parse_iso_datetime(row["created_at"]),
        )

    def upsert_capa(self, capa: IncidentCapa) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT capa_id FROM incident_capas WHERE incident_id = ?",
                (capa.incident_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO incident_capas (
                        capa_id, incident_id, status, trigger_reason, goal, description, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        capa.capa_id,
                        capa.incident_id,
                        capa.status.value,
                        capa.trigger_reason,
                        capa.goal,
                        capa.description,
                        _dt_iso(capa.created_at),
                        _dt_iso(capa.updated_at),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE incident_capas SET status = ?, trigger_reason = ?, goal = ?,
                        description = ?, updated_at = ? WHERE capa_id = ?
                    """,
                    (
                        capa.status.value,
                        capa.trigger_reason,
                        capa.goal,
                        capa.description,
                        _dt_iso(capa.updated_at),
                        capa.capa_id,
                    ),
                )
            conn.commit()

    def get_capa(self, incident_id: str) -> IncidentCapa | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM incident_capas WHERE incident_id = ?", (incident_id,)).fetchone()
        if row is None:
            return None
        return IncidentCapa(
            capa_id=row["capa_id"],
            incident_id=row["incident_id"],
            status=CapaStatus(row["status"]),
            trigger_reason=row["trigger_reason"],
            goal=row["goal"],
            description=row["description"],
            created_at=parse_iso_datetime(row["created_at"]),
            updated_at=parse_iso_datetime(row["updated_at"]),
        )

    def upsert_rca(self, rca: RootCauseAnalysis) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT rca_id FROM root_cause_analyses WHERE incident_id = ?",
                (rca.incident_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO root_cause_analyses (
                        rca_id, incident_id, immediate_event, trigger, root_causes,
                        similar_prior, systemic_weakness, future_risk, method, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rca.rca_id,
                        rca.incident_id,
                        rca.immediate_event,
                        rca.trigger,
                        rca.root_causes,
                        rca.similar_prior,
                        rca.systemic_weakness,
                        rca.future_risk,
                        rca.method,
                        _dt_iso(rca.created_at),
                        _dt_iso(rca.updated_at),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE root_cause_analyses SET immediate_event = ?, trigger = ?, root_causes = ?,
                        similar_prior = ?, systemic_weakness = ?, future_risk = ?, method = ?,
                        updated_at = ? WHERE rca_id = ?
                    """,
                    (
                        rca.immediate_event,
                        rca.trigger,
                        rca.root_causes,
                        rca.similar_prior,
                        rca.systemic_weakness,
                        rca.future_risk,
                        rca.method,
                        _dt_iso(rca.updated_at),
                        rca.rca_id,
                    ),
                )
            conn.commit()

    def get_rca(self, incident_id: str) -> RootCauseAnalysis | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM root_cause_analyses WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return RootCauseAnalysis(
            rca_id=row["rca_id"],
            incident_id=row["incident_id"],
            immediate_event=row["immediate_event"],
            trigger=row["trigger"],
            root_causes=row["root_causes"],
            similar_prior=row["similar_prior"],
            systemic_weakness=row["systemic_weakness"],
            future_risk=row["future_risk"],
            method=row["method"],
            created_at=parse_iso_datetime(row["created_at"]),
            updated_at=parse_iso_datetime(row["updated_at"]),
        )

    def add_effectiveness_review(self, review: EffectivenessReview) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO effectiveness_reviews (
                    review_id, incident_id, planned_at, criteria, completed_at,
                    completed_by_user_id, result, effective, notes, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.review_id,
                    review.incident_id,
                    _dt_iso(review.planned_at),
                    review.criteria,
                    _dt_iso(review.completed_at),
                    review.completed_by_user_id,
                    review.result,
                    int(review.effective) if review.effective is not None else None,
                    review.notes,
                    review.status.value,
                    _dt_iso(review.created_at),
                ),
            )
            conn.commit()

    def update_effectiveness_review(self, review: EffectivenessReview) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE effectiveness_reviews SET completed_at = ?, completed_by_user_id = ?,
                    result = ?, effective = ?, notes = ?, status = ? WHERE review_id = ?
                """,
                (
                    _dt_iso(review.completed_at),
                    review.completed_by_user_id,
                    review.result,
                    int(review.effective) if review.effective is not None else None,
                    review.notes,
                    review.status.value,
                    review.review_id,
                ),
            )
            conn.commit()

    def get_effectiveness_review(self, incident_id: str) -> EffectivenessReview | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM effectiveness_reviews WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_effectiveness_review(row)

    def _row_to_effectiveness_review(self, row: sqlite3.Row) -> EffectivenessReview:
        return EffectivenessReview(
            review_id=row["review_id"],
            incident_id=row["incident_id"],
            planned_at=parse_iso_datetime(row["planned_at"]),
            criteria=row["criteria"],
            completed_at=_dt_parse(row["completed_at"]),
            completed_by_user_id=row["completed_by_user_id"],
            result=row["result"],
            effective=bool(row["effective"]) if row["effective"] is not None else None,
            notes=row["notes"],
            status=EffectivenessReviewStatus(row["status"]),
            created_at=parse_iso_datetime(row["created_at"]),
        )

    def list_pending_effectiveness_reviews(self) -> list[EffectivenessReview]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM effectiveness_reviews WHERE status = ? ORDER BY planned_at ASC",
                (EffectivenessReviewStatus.PLANNED.value,),
            ).fetchall()
        return [self._row_to_effectiveness_review(r) for r in rows]

    def add_artifact(self, artifact: IncidentArtifact) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incident_artifacts (
                    artifact_id, incident_id, artifact_type, storage_key, original_filename,
                    mime_type, sha256, size_bytes, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.incident_id,
                    artifact.artifact_type.value,
                    artifact.storage_key,
                    artifact.original_filename,
                    artifact.mime_type,
                    artifact.sha256,
                    artifact.size_bytes,
                    json.dumps(artifact.metadata, ensure_ascii=True, sort_keys=True),
                    _dt_iso(artifact.created_at),
                ),
            )
            conn.commit()

    def list_artifacts(self, incident_id: str) -> list[IncidentArtifact]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_artifacts WHERE incident_id = ? ORDER BY created_at ASC",
                (incident_id,),
            ).fetchall()
        result: list[IncidentArtifact] = []
        for row in rows:
            result.append(
                IncidentArtifact(
                    artifact_id=row["artifact_id"],
                    incident_id=row["incident_id"],
                    artifact_type=ArtifactType(row["artifact_type"]),
                    storage_key=row["storage_key"],
                    original_filename=row["original_filename"],
                    mime_type=row["mime_type"],
                    sha256=row["sha256"],
                    size_bytes=row["size_bytes"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                    created_at=parse_iso_datetime(row["created_at"]),
                )
            )
        return result

    def insert_group(self, group: IncidentGroup) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incident_groups (group_id, name, description, created_by_user_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    group.group_id,
                    group.name,
                    group.description,
                    group.created_by_user_id,
                    _dt_iso(group.created_at),
                ),
            )
            conn.commit()

    def get_group(self, group_id: str) -> IncidentGroup:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM incident_groups WHERE group_id = ?", (group_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"group not found: {group_id}")
        return IncidentGroup(
            group_id=row["group_id"],
            name=row["name"],
            description=row["description"],
            created_by_user_id=row["created_by_user_id"],
            created_at=parse_iso_datetime(row["created_at"]),
        )

    def add_leadership_ack(self, ack: LeadershipAcknowledgement) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO leadership_acknowledgements (
                    ack_id, incident_id, forwarded_by_user_id, forwarded_at,
                    leadership_user_id, comment, acknowledged_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ack.ack_id,
                    ack.incident_id,
                    ack.forwarded_by_user_id,
                    _dt_iso(ack.forwarded_at),
                    ack.leadership_user_id,
                    ack.comment,
                    _dt_iso(ack.acknowledged_at),
                    ack.status.value,
                ),
            )
            conn.commit()

    def update_leadership_ack(self, ack: LeadershipAcknowledgement) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE leadership_acknowledgements SET comment = ?, acknowledged_at = ?, status = ?
                WHERE ack_id = ?
                """,
                (
                    ack.comment,
                    _dt_iso(ack.acknowledged_at),
                    ack.status.value,
                    ack.ack_id,
                ),
            )
            conn.commit()

    def get_leadership_ack(self, incident_id: str) -> LeadershipAcknowledgement | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM leadership_acknowledgements WHERE incident_id = ? ORDER BY forwarded_at DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return LeadershipAcknowledgement(
            ack_id=row["ack_id"],
            incident_id=row["incident_id"],
            forwarded_by_user_id=row["forwarded_by_user_id"],
            forwarded_at=parse_iso_datetime(row["forwarded_at"]),
            leadership_user_id=row["leadership_user_id"],
            comment=row["comment"],
            acknowledged_at=_dt_parse(row["acknowledged_at"]),
            status=LeadershipAckStatus(row["status"]),
        )

    def list_leadership_queue(self, leadership_user_id: str) -> list[LeadershipAcknowledgement]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM leadership_acknowledgements
                WHERE leadership_user_id = ? ORDER BY forwarded_at DESC
                """,
                (leadership_user_id,),
            ).fetchall()
        result: list[LeadershipAcknowledgement] = []
        for row in rows:
            result.append(
                LeadershipAcknowledgement(
                    ack_id=row["ack_id"],
                    incident_id=row["incident_id"],
                    forwarded_by_user_id=row["forwarded_by_user_id"],
                    forwarded_at=parse_iso_datetime(row["forwarded_at"]),
                    leadership_user_id=row["leadership_user_id"],
                    comment=row["comment"],
                    acknowledged_at=_dt_parse(row["acknowledged_at"]),
                    status=LeadershipAckStatus(row["status"]),
                )
            )
        return result

    def insert_management_batch(self, batch: ManagementReviewBatch) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO management_review_batches (
                    batch_id, period_start, period_end, status, created_by_user_id, created_at, report_storage_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.batch_id,
                    _dt_iso(batch.period_start),
                    _dt_iso(batch.period_end),
                    batch.status.value,
                    batch.created_by_user_id,
                    _dt_iso(batch.created_at),
                    batch.report_storage_key,
                ),
            )
            conn.commit()

    def update_management_batch(self, batch: ManagementReviewBatch) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE management_review_batches SET status = ?, report_storage_key = ? WHERE batch_id = ?
                """,
                (batch.status.value, batch.report_storage_key, batch.batch_id),
            )
            conn.commit()

    def get_management_batch(self, batch_id: str) -> ManagementReviewBatch:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM management_review_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"management review batch not found: {batch_id}")
        return ManagementReviewBatch(
            batch_id=row["batch_id"],
            period_start=parse_iso_datetime(row["period_start"]),
            period_end=parse_iso_datetime(row["period_end"]),
            status=ManagementReviewBatchStatus(row["status"]),
            created_by_user_id=row["created_by_user_id"],
            created_at=parse_iso_datetime(row["created_at"]),
            report_storage_key=row["report_storage_key"],
        )

    def insert_management_item(self, item: ManagementReviewItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO management_review_items (
                    item_id, batch_id, incident_id, status, acknowledged_at, acknowledged_by_user_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.item_id,
                    item.batch_id,
                    item.incident_id,
                    item.status.value,
                    _dt_iso(item.acknowledged_at),
                    item.acknowledged_by_user_id,
                ),
            )
            conn.commit()

    def update_management_item(self, item: ManagementReviewItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE management_review_items SET status = ?, acknowledged_at = ?, acknowledged_by_user_id = ?
                WHERE item_id = ?
                """,
                (
                    item.status.value,
                    _dt_iso(item.acknowledged_at),
                    item.acknowledged_by_user_id,
                    item.item_id,
                ),
            )
            conn.commit()

    def list_management_items(self, batch_id: str) -> list[ManagementReviewItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM management_review_items WHERE batch_id = ? ORDER BY incident_id ASC",
                (batch_id,),
            ).fetchall()
        result: list[ManagementReviewItem] = []
        for row in rows:
            result.append(
                ManagementReviewItem(
                    item_id=row["item_id"],
                    batch_id=row["batch_id"],
                    incident_id=row["incident_id"],
                    status=ManagementReviewItemStatus(row["status"]),
                    acknowledged_at=_dt_parse(row["acknowledged_at"]),
                    acknowledged_by_user_id=row["acknowledged_by_user_id"],
                )
            )
        return result

    def list_incidents_in_period(self, period_start: datetime, period_end: datetime) -> list[IncidentCase]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM incidents
                WHERE reported_at >= ? AND reported_at <= ?
                ORDER BY reported_at ASC, incident_id ASC
                """,
                (_dt_iso(period_start), _dt_iso(period_end)),
            ).fetchall()
        return [self._row_to_case(r) for r in rows]

    def upsert_module_role(self, assignment: ModuleRoleAssignment) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO module_role_assignments (
                    assignment_id, user_id, role_name, assigned_by_user_id, assigned_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, role_name) DO UPDATE SET
                    assigned_by_user_id = excluded.assigned_by_user_id,
                    assigned_at = excluded.assigned_at
                """,
                (
                    assignment.assignment_id,
                    assignment.user_id,
                    assignment.role_name.value,
                    assignment.assigned_by_user_id,
                    _dt_iso(assignment.assigned_at),
                ),
            )
            conn.commit()

    def list_module_roles(self, role_name: ModuleInternalRole | None = None) -> list[ModuleRoleAssignment]:
        with self._connect() as conn:
            if role_name is None:
                rows = conn.execute(
                    "SELECT * FROM module_role_assignments ORDER BY assigned_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM module_role_assignments WHERE role_name = ? ORDER BY assigned_at DESC",
                    (role_name.value,),
                ).fetchall()
        result: list[ModuleRoleAssignment] = []
        for row in rows:
            result.append(
                ModuleRoleAssignment(
                    assignment_id=row["assignment_id"],
                    user_id=row["user_id"],
                    role_name=ModuleInternalRole(row["role_name"]),
                    assigned_by_user_id=row["assigned_by_user_id"],
                    assigned_at=parse_iso_datetime(row["assigned_at"]),
                )
            )
        return result

    def list_open_actions(self, incident_id: str) -> list[IncidentAction]:
        actions = self.list_actions(incident_id)
        return [a for a in actions if a.status != ActionStatus.COMPLETED]

    def count_open_inquiries(self, incident_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM incident_inquiries WHERE incident_id = ? AND status = ?",
                (incident_id, InquiryStatus.OPEN.value),
            ).fetchone()
        return int(row["c"]) if row else 0
