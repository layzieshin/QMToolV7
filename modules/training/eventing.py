"""Training module event subscriptions (started only when module license is valid)."""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import TrainingProgress


def subscribe_training_events(container) -> None:
    if not container.has_port("training_runtime_deps"):
        return
    deps = container.get_port("training_runtime_deps")
    snapshot_repo = deps["snapshot_repo"]
    documents_read_api = deps["documents_read_api"]
    event_bus = deps["event_bus"]

    def _on_read_confirmed(envelope) -> None:
        payload = envelope.payload
        user_id = payload.get("user_id")
        document_id = payload.get("document_id")
        version = payload.get("version")
        if not user_id or not document_id or version is None:
            return
        try:
            receipt = documents_read_api.get_read_receipt(user_id, document_id, int(version))
        except Exception:
            return
        if receipt is None:
            return
        if str(getattr(receipt, "user_id", "")) != str(user_id):
            return
        if str(getattr(receipt, "document_id", "")) != str(document_id):
            return
        if int(getattr(receipt, "version", -1)) != int(version):
            return
        progress = snapshot_repo.get_progress(user_id, document_id, int(version))
        if progress is not None and progress.read_confirmed_at is not None:
            return
        now = datetime.now(timezone.utc)
        new_progress = TrainingProgress(
            user_id=user_id,
            document_id=document_id,
            version=int(version),
            read_confirmed_at=now,
            quiz_passed_at=progress.quiz_passed_at if progress else None,
            last_score=progress.last_score if progress else None,
            quiz_attempts_count=progress.quiz_attempts_count if progress else 0,
        )
        snapshot_repo.upsert_progress(new_progress)

    subscribe = getattr(event_bus, "subscribe", None)
    if callable(subscribe):
        subscribe("domain.documents.read.confirmed.v1", _on_read_confirmed)
