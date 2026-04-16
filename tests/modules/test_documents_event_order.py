from __future__ import annotations

import unittest

from modules.documents.contracts import (
    ControlClass,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    WorkflowProfile,
)
from modules.documents.workflow_use_cases import DocumentsWorkflowUseCases


class _ServiceDouble:
    def __init__(self) -> None:
        self.calls: list[str] = []

    # guards / validators
    def _ensure_owner_or_privileged(self, *_args, **_kwargs):
        return None

    def _assert_profile(self, *_args, **_kwargs):
        return None

    def _assert_assignments_for_profile(self, *_args, **_kwargs):
        return None

    # workflow helpers
    @staticmethod
    def _next_status_from_profile(profile: WorkflowProfile | None, status: DocumentStatus) -> DocumentStatus:
        if status == DocumentStatus.PLANNED:
            return DocumentStatus.IN_PROGRESS
        return status

    # IO hooks
    def _store_state(self, *_args, **_kwargs):
        self.calls.append("store")

    def _publish(self, *_args, **_kwargs):
        self.calls.append("publish")
        from qm_platform.events.event_envelope import EventEnvelope

        return EventEnvelope.create(
            name="domain.documents.workflow.started.v1",
            module_id="documents",
            payload={"document_id": "DOC-1", "version": 1},
        )

    def _sync_registry(self, *_args, **_kwargs):
        self.calls.append("sync")

    def _emit_audit(self, *_args, **_kwargs):
        self.calls.append("audit")


class DocumentsEventOrderTest(unittest.TestCase):
    def test_start_workflow_persists_before_publish(self) -> None:
        svc = _ServiceDouble()
        uc = DocumentsWorkflowUseCases(svc)
        state = DocumentVersionState(
            document_id="DOC-1",
            version=1,
            title="Doc",
            status=DocumentStatus.PLANNED,
            doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED,
        )
        profile = WorkflowProfile.long_release_path()

        uc.start_workflow(state, profile)

        # Expect at least one persistence call before first publish.
        first_store_idx = svc.calls.index("store")
        first_publish_idx = svc.calls.index("publish")
        self.assertLess(first_store_idx, first_publish_idx)


if __name__ == "__main__":
    unittest.main()

