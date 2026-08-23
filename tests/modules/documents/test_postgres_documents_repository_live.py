"""Live PostgreSQL repository tests for AP-029 PG01-C documents."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from modules.documents import postgres_schema as documents_schema
from modules.documents.contracts import (
    ControlClass,
    DocumentHeader,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    WorkflowCommentContext,
    WorkflowCommentRecord,
    WorkflowCommentSourceKind,
    WorkflowCommentStatus,
)
from modules.documents.postgres_connection import PostgresRepositoryError
from modules.documents.postgres_repository import PostgresDocumentsRepository
from modules.documents.sqlite_repository import SQLiteDocumentsRepository
from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


@pytest.fixture
def documents_repository(live_postgres_env: LivePostgresEnv) -> PostgresDocumentsRepository:
    documents_schema.provision_documents_schema(live_postgres_env.admin_dsn)
    documents_schema.migrate_documents_schema(live_postgres_env.migrator_dsn)
    repository = PostgresDocumentsRepository(live_postgres_env.runtime_dsn)
    yield repository
    with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS documents CASCADE")


def _sample_header(document_id: str = "DOC-PG-1") -> DocumentHeader:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return DocumentHeader(
        document_id=document_id,
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
        created_at=moment,
        updated_at=moment,
    )


def _sample_state(document_id: str = "DOC-PG-1", version: int = 1) -> DocumentVersionState:
    moment = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    return DocumentVersionState(
        document_id=document_id,
        version=version,
        title="PG01-C live document",
        description="parity sample",
        doc_type=DocumentType.VA,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="long_release",
        owner_user_id="user-1",
        status=DocumentStatus.IN_PROGRESS,
        workflow_active=True,
        created_at=moment,
        created_by="user-1",
        last_event_id="evt-pg-1",
        last_event_at=moment,
        last_actor_user_id="user-1",
    )


def _sample_comment(document_id: str = "DOC-PG-1", version: int = 1) -> WorkflowCommentRecord:
    moment = datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)
    return WorkflowCommentRecord(
        comment_id="cmt-pg-1",
        ref_no="C-1",
        document_id=document_id,
        version=version,
        context=WorkflowCommentContext.PDF_REVIEW,
        source_kind=WorkflowCommentSourceKind.PDF_APP,
        source_comment_key="manual:cmt-pg-1",
        artifact_id=None,
        page_number=2,
        anchor_json='{"x":1,"y":2}',
        author_display="Reviewer",
        source_created_at=moment,
        preview_text="needs fix",
        full_text="needs fix on page 2",
        status=WorkflowCommentStatus.ACTIVE,
        status_note=None,
        status_changed_by=None,
        status_changed_at=None,
        created_at=moment,
        updated_at=moment,
    )


def test_postgres_documents_repository_crud_roundtrip(
    documents_repository: PostgresDocumentsRepository,
) -> None:
    header = _sample_header()
    state = _sample_state()
    documents_repository.upsert_header(header)
    documents_repository.upsert(state)

    loaded_header = documents_repository.get_header("DOC-PG-1")
    loaded_state = documents_repository.get("DOC-PG-1", 1)
    assert loaded_header is not None
    assert loaded_header.document_id == header.document_id
    assert loaded_header.doc_type == header.doc_type
    assert loaded_header.workflow_profile_id == header.workflow_profile_id
    assert loaded_state is not None
    assert loaded_state.document_id == state.document_id
    assert loaded_state.version == state.version
    assert loaded_state.title == state.title
    assert loaded_state.status == state.status
    assert documents_repository.list_versions("DOC-PG-1")[0].title == state.title


def test_postgres_documents_repository_matches_sqlite_reference(
    documents_repository: PostgresDocumentsRepository,
) -> None:
    header = _sample_header("DOC-PARITY")
    state = _sample_state("DOC-PARITY", 1)
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_repo = SQLiteDocumentsRepository(Path(tmp) / "documents.db")
        sqlite_repo.upsert_header(header)
        sqlite_repo.upsert(state)
        documents_repository.upsert_header(header)
        documents_repository.upsert(state)
        sqlite_loaded = sqlite_repo.get("DOC-PARITY", 1)
        pg_loaded = documents_repository.get("DOC-PARITY", 1)
        assert sqlite_loaded is not None and pg_loaded is not None
        assert sqlite_loaded.document_id == pg_loaded.document_id
        assert sqlite_loaded.version == pg_loaded.version
        assert sqlite_loaded.title == pg_loaded.title
        assert sqlite_loaded.status == pg_loaded.status
        assert sqlite_loaded.workflow_profile_id == pg_loaded.workflow_profile_id


def test_postgres_documents_workflow_comment_persist(
    documents_repository: PostgresDocumentsRepository,
) -> None:
    documents_repository.upsert_header(_sample_header())
    documents_repository.upsert(_sample_state())
    comment = _sample_comment()
    documents_repository.upsert_workflow_comment(comment)
    loaded = documents_repository.get_workflow_comment("cmt-pg-1")
    assert loaded is not None
    assert loaded.preview_text == comment.preview_text
    assert loaded.anchor_json == comment.anchor_json
    assert loaded.status == WorkflowCommentStatus.ACTIVE
    listed = documents_repository.list_workflow_comments(
        "DOC-PG-1", 1, WorkflowCommentContext.PDF_REVIEW
    )
    assert [item.comment_id for item in listed] == ["cmt-pg-1"]


def test_postgres_documents_write_transaction_commit_and_rollback(
    documents_repository: PostgresDocumentsRepository,
) -> None:
    with documents_repository.write_transaction():
        documents_repository.upsert_header(_sample_header("DOC-TXN"))
        documents_repository.upsert(_sample_state("DOC-TXN", 1))
    assert documents_repository.get("DOC-TXN", 1) is not None

    with pytest.raises(RuntimeError, match="forced-rollback"):
        with documents_repository.write_transaction():
            documents_repository.upsert(_sample_state("DOC-TXN", 2))
            raise RuntimeError("forced-rollback")
    assert documents_repository.get("DOC-TXN", 2) is None
    assert documents_repository.get("DOC-TXN", 1) is not None


def test_postgres_documents_repository_rejects_migrator_login(
    live_postgres_env: LivePostgresEnv,
) -> None:
    documents_schema.provision_documents_schema(live_postgres_env.admin_dsn)
    documents_schema.migrate_documents_schema(live_postgres_env.migrator_dsn)
    repository = PostgresDocumentsRepository(live_postgres_env.migrator_dsn)
    try:
        with pytest.raises(PostgresRepositoryError):
            repository.list_by_status(DocumentStatus.IN_PROGRESS)
    finally:
        with psycopg.connect(live_postgres_env.admin_dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS documents CASCADE")


def test_postgres_workflow_profile_store_roundtrip(
    documents_repository: PostgresDocumentsRepository,
) -> None:
    from modules.documents.bootstrap_provenance import DocumentsBootstrapProvenance
    from modules.documents.workflow_profile_store import (
        WorkflowProfileRelationalStore,
        WorkflowProfileTransitionDefinition,
        WorkflowProfileVersionDefinition,
    )

    seed_path = Path("modules/documents/workflow_profiles.json")
    store = WorkflowProfileRelationalStore(
        documents_repository,
        bundled_seed_path=seed_path,
        legacy_profiles_path=seed_path,
        bootstrap_provenance=DocumentsBootstrapProvenance.FRESH_INSTALL,
    )
    payload = WorkflowProfileVersionDefinition(
        profile_code="pg_live_profile",
        label="PG Live Profile",
        control_class=ControlClass.CONTROLLED,
        release_evidence_mode="WORKFLOW",
        requires_editors=True,
        requires_reviewers=True,
        requires_approvers=True,
        allows_content_changes=False,
        transitions=(
            WorkflowProfileTransitionDefinition(
                transition_no=1,
                from_status="DRAFT",
                to_status="IN_REVIEW",
                required_role="EDITOR",
                decision_policy="ONE_OF_POOL",
                signature_required=True,
                four_eyes_required=False,
                revoke_if_changed=False,
                deadline_seconds=None,
                is_enabled=True,
            ),
            WorkflowProfileTransitionDefinition(
                transition_no=2,
                from_status="IN_REVIEW",
                to_status="IN_APPROVAL",
                required_role="REVIEWER",
                decision_policy="ONE_OF_POOL",
                signature_required=True,
                four_eyes_required=False,
                revoke_if_changed=False,
                deadline_seconds=None,
                is_enabled=True,
            ),
            WorkflowProfileTransitionDefinition(
                transition_no=3,
                from_status="IN_APPROVAL",
                to_status="APPROVED",
                required_role="APPROVER",
                decision_policy="ONE_OF_POOL",
                signature_required=True,
                four_eyes_required=True,
                revoke_if_changed=False,
                deadline_seconds=None,
                is_enabled=True,
            ),
        ),
    )
    created = store.create_definition(
        payload,
        source_kind="ADMIN",
        change_reason="hr2-live-profile",
        actor_user_id="live-tester",
    )
    assert created["profile_code"] == "pg_live_profile"
    loaded = store.get_active_definition("pg_live_profile")
    assert loaded.requires_editors is True
    assert loaded.requires_reviewers is True
    assert loaded.requires_approvers is True
    assert loaded.allows_content_changes is False
    assert loaded.four_eyes_required is True
    assert [item.transition_no for item in loaded.transitions] == [1, 2, 3]
    assert loaded.transitions[0].signature_required is True
    assert loaded.transitions[0].four_eyes_required is False
    assert loaded.transitions[0].deadline_seconds is None
    assert loaded.transitions[2].four_eyes_required is True
    assert loaded.transitions[2].is_enabled is True
