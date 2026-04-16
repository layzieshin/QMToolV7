"""Presenter for document detail formatting and history row building.

Extracted from documents_workflow_view.py (Phase 3A).
"""
from __future__ import annotations


class DocumentsDetailPresenter:
    """Pure logic: no Qt imports, no side-effects."""

    @staticmethod
    def format_dt(dt: object) -> str:
        """Format a datetime to German locale string, returns '-' for None."""
        if dt is None:
            return "-"
        try:
            return dt.strftime("%d.%m.%Y %H:%M")  # type: ignore[union-attr]
        except Exception:
            return str(dt)

    @staticmethod
    def document_code(state: object) -> str:
        custom_fields = getattr(state, "custom_fields", {}) or {}
        code = custom_fields.get("document_code")
        return str(code) if code else str(getattr(state, "document_id", ""))

    @staticmethod
    def overview_rows(state: object, header: object) -> list[tuple[str, str]]:
        fmt = DocumentsDetailPresenter.format_dt
        code = DocumentsDetailPresenter.document_code
        return [
            ("Dokumentenkennung", code(state)),
            ("Version", str(state.version)),
            ("Titel", state.title or ""),
            ("Status", state.status.value),
            ("Owner / Erstellt von", str(state.created_by or state.owner_user_id or "-")),
            ("Erstellt am", fmt(state.created_at)),
            ("Workflow aktiv", "Ja" if state.workflow_active else "Nein"),
            ("Workflowprofil", state.workflow_profile_id or "-"),
            ("Dokumenttyp", state.doc_type.value),
            ("Kontrollklasse", state.control_class.value),
            ("Department", str(getattr(header, "department", "") or "-")),
            ("Standort", str(getattr(header, "site", "") or "-")),
            ("Regulatory Scope", str(getattr(header, "regulatory_scope", "") or "-")),
            ("── Prüfung ──", ""),
            ("Geprüft am", fmt(state.review_completed_at)),
            ("Geprüft durch", str(state.review_completed_by or "-")),
            ("── Freigabe ──", ""),
            ("Freigegeben am", fmt(state.released_at or state.approval_completed_at)),
            ("Freigegeben durch", str(state.approval_completed_by or "-")),
            ("Gültig ab", fmt(state.valid_from)),
            ("Gültig bis", fmt(state.valid_until)),
            ("Nächste Prüfung", fmt(state.next_review_at)),
            ("── Archivierung ──", ""),
            ("Archiviert am", fmt(state.archived_at)),
            ("Archiviert durch", str(state.archived_by or "-")),
            ("── Letzte Änderung ──", ""),
            ("Zuletzt geändert am", fmt(state.last_event_at)),
            ("Zuletzt geändert durch", str(state.last_actor_user_id or "-")),
            ("Letztes Event-ID", str(state.last_event_id or "-")),
        ]

    @staticmethod
    def roles_rows(state: object) -> list[tuple[str, str]]:
        return [
            ("Editoren", ", ".join(sorted(state.assignments.editors)) or "-"),
            ("Pruefer", ", ".join(sorted(state.assignments.reviewers)) or "-"),
            ("Freigeber", ", ".join(sorted(state.assignments.approvers)) or "-"),
            ("Naechster Schritt", "Workflowsteuerung unten blendet Aktionen status- und rollenabhaengig ein."),
        ]

    @staticmethod
    def history_rows(state: object) -> list[tuple[str, str, str, str, str]]:
        """Build history rows from state timestamps. Returns primary rows or fallback."""
        rows: list[tuple[str, str, str, str, str]] = []
        if state.created_at:
            rows.append((
                str(state.created_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Version angelegt",
                str(state.created_by or state.owner_user_id or "-"),
                "PLANNED",
                f"Profil: {state.workflow_profile_id or '-'}",
            ))
        if state.released_at:
            rows.append((
                str(state.released_at.strftime("%Y-%m-%d %H:%M:%S") if state.released_at else "-"),
                "Freigegeben",
                str(state.last_actor_user_id or "-"),
                "APPROVED",
                "",
            ))
        if state.approval_completed_at:
            rows.append((
                str(state.approval_completed_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Freigabe abgeschlossen",
                str(state.approval_completed_by or "-"),
                "IN_APPROVAL->APPROVED",
                "",
            ))
        if state.review_completed_at:
            rows.append((
                str(state.review_completed_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Pruefung abgeschlossen",
                str(state.review_completed_by or "-"),
                "IN_REVIEW->IN_APPROVAL",
                "",
            ))
        if state.last_event_at and state.last_event_id:
            rows.append((
                str(state.last_event_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Letzte Aenderung",
                str(state.last_actor_user_id or "-"),
                str(state.last_event_id or "-"),
                f"Extension Count: {state.extension_count}" if state.extension_count > 0 else "",
            ))
        if state.archived_at:
            rows.append((
                str(state.archived_at.strftime("%Y-%m-%d %H:%M:%S")),
                "Archiviert",
                str(state.archived_by or "-"),
                "APPROVED->ARCHIVED",
                "",
            ))
        if rows:
            return rows
        # Fallback
        return [
            (str(state.last_event_at or "-"), "Letztes Event", str(state.last_actor_user_id or "-"), str(state.last_event_id or "-"), ""),
            (str(state.review_completed_at or "-"), "Pruefung abgeschlossen", str(state.review_completed_by or "-"), "", ""),
            (str(state.approval_completed_at or "-"), "Freigabe abgeschlossen", str(state.approval_completed_by or "-"), "", ""),
            (str(state.released_at or "-"), "Freigegeben", str(state.last_actor_user_id or "-"), "", ""),
            (str(state.archived_at or "-"), "Archiviert", str(state.archived_by or "-"), "", ""),
        ]

