"""Reads released documents from the documents module (§3.1)."""
from __future__ import annotations

from modules.documents.contracts import DocumentStatus

from .contracts import TrainingDocumentRef


class ReleasedDocumentCatalogReader:
    def __init__(self, *, documents_pool_api: object) -> None:
        self._pool = documents_pool_api

    def list_released_documents(self) -> list[TrainingDocumentRef]:
        refs: list[TrainingDocumentRef] = []
        for state in self._pool.list_by_status(DocumentStatus.APPROVED):
            if getattr(state, "superseded_by_version", None) is not None:
                continue
            header = self._pool.get_header(state.document_id)
            refs.append(
                TrainingDocumentRef(
                    document_id=state.document_id,
                    version=state.version,
                    title=state.title,
                    owner_user_id=state.owner_user_id,
                    released_at=getattr(state, "released_at", None),
                    department=getattr(header, "department", None) if header else None,
                    site=getattr(header, "site", None) if header else None,
                    regulatory_scope=getattr(header, "regulatory_scope", None) if header else None,
                )
            )
        return refs

