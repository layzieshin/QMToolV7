"""Training report service – statistics, audit, matrix export (§3.14)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import (
    TrainingAuditLogItem,
    TrainingMatrixExportResult,
    TrainingStatistics,
)
from .training_report_repository import TrainingReportRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingReportService:
    def __init__(
        self,
        *,
        report_repo: TrainingReportRepository,
        event_bus: object | None = None,
    ) -> None:
        self._repo = report_repo
        self._event_bus = event_bus

    def get_training_statistics(self) -> TrainingStatistics:
        counts = self._repo.count_snapshots_by_status()
        total = counts.get("total", 0)
        completed = counts.get("completed", 0)
        read_only = counts.get("read_only", 0)
        failed = max(0, total - completed - read_only)
        # Count distinct users from audit / snapshots – simplified
        return TrainingStatistics(
            total_users=0,  # enriched later if needed
            total_assignments=total,
            completed=completed,
            open=read_only,
            failed=failed,
        )

    def list_training_audit_log(self) -> list[TrainingAuditLogItem]:
        return self._repo.list_audit_log()

    def log_action(self, action: str, actor_user_id: str, details: dict | None = None) -> None:
        item = TrainingAuditLogItem(
            log_id=uuid4().hex,
            action=action,
            actor_user_id=actor_user_id,
            timestamp=_utcnow(),
            details=details or {},
        )
        self._repo.add_audit_entry(item)

    def export_training_matrix(self) -> TrainingMatrixExportResult:
        rows = self._repo.export_matrix_rows()
        now = _utcnow()
        export_id = uuid4().hex
        result = TrainingMatrixExportResult(
            export_id=export_id,
            row_count=len(rows),
            exported_at=now,
            rows=rows,
        )
        self.log_action("matrix_export", "system", {"export_id": export_id, "row_count": len(rows)})
        self._publish("domain.training.matrix.exported.v1", {
            "export_id": export_id, "row_count": len(rows),
        })
        return result

    def _publish(self, name: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload))

