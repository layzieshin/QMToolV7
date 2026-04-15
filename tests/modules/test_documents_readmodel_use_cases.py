from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from modules.documents.contracts import DocumentStatus
from modules.documents.readmodel_use_cases import DocumentsReadmodelUseCases


@dataclass
class _StubState:
    document_id: str
    version: int
    title: str
    status: DocumentStatus
    owner_user_id: str | None
    last_event_at: datetime | None


def _always_visible(_state: object, _user_id: str, _role: str) -> bool:
    return True


def test_recent_documents_sort_handles_mixed_naive_aware_and_none() -> None:
    states = [
        _StubState(
            document_id="DOC-NONE",
            version=1,
            title="none",
            status=DocumentStatus.PLANNED,
            owner_user_id="u",
            last_event_at=None,
        ),
        _StubState(
            document_id="DOC-NAIVE",
            version=1,
            title="naive",
            status=DocumentStatus.PLANNED,
            owner_user_id="u",
            last_event_at=datetime(2026, 4, 15, 10, 0, 0),
        ),
        _StubState(
            document_id="DOC-AWARE",
            version=1,
            title="aware",
            status=DocumentStatus.PLANNED,
            owner_user_id="u",
            last_event_at=datetime(2026, 4, 15, 11, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    use_cases = DocumentsReadmodelUseCases(iter_states=lambda: states, matches_user_context=_always_visible)

    rows = use_cases.list_recent_documents_for_user("u", "USER")

    assert [row.document_id for row in rows] == ["DOC-AWARE", "DOC-NAIVE", "DOC-NONE"]


def test_recent_documents_sort_normalizes_timezone_offsets() -> None:
    tz_plus_2 = timezone(timedelta(hours=2))
    states = [
        _StubState(
            document_id="DOC-UTC-0730",
            version=1,
            title="utc",
            status=DocumentStatus.PLANNED,
            owner_user_id="u",
            last_event_at=datetime(2026, 4, 15, 7, 30, 0, tzinfo=timezone.utc),
        ),
        _StubState(
            document_id="DOC-PLUS2-1000",
            version=1,
            title="plus2",
            status=DocumentStatus.PLANNED,
            owner_user_id="u",
            last_event_at=datetime(2026, 4, 15, 10, 0, 0, tzinfo=tz_plus_2),
        ),
    ]
    use_cases = DocumentsReadmodelUseCases(iter_states=lambda: states, matches_user_context=_always_visible)

    rows = use_cases.list_recent_documents_for_user("u", "USER")

    # 10:00+02:00 equals 08:00 UTC and must be newer than 07:30 UTC
    assert [row.document_id for row in rows] == ["DOC-PLUS2-1000", "DOC-UTC-0730"]

