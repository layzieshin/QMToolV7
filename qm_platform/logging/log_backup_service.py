from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class LogBackupResult:
    zip_path: Path
    audit_lines: int
    platform_lines: int
    cutoff_utc: datetime


class LogBackupService:
    def __init__(
        self,
        *,
        platform_log_file: Path,
        audit_log_file: Path,
        backup_dir: Path,
        state_file: Path,
        audit_logger=None,
    ) -> None:
        self._platform_log_file = platform_log_file
        self._audit_log_file = audit_log_file
        self._backup_dir = backup_dir
        self._state_file = state_file
        self._audit_logger = audit_logger

    def create_backup(self, target_dir: Path | None = None, actor: str = "system") -> LogBackupResult:
        backup_dir = target_dir or self._backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        cutoff = datetime.now(timezone.utc)
        previous_cutoff = self.get_last_backup_utc()
        audit_rows = self._read_since(self._audit_log_file, previous_cutoff, cutoff)
        platform_rows = self._read_since(self._platform_log_file, previous_cutoff, cutoff)
        zip_path = backup_dir / f"logs_backup_{cutoff.strftime('%Y%m%d_%H%M%S')}.zip"
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(
                f"audit_{cutoff.strftime('%Y%m%d_%H%M')}.jsonl",
                "\n".join(audit_rows) + ("\n" if audit_rows else ""),
            )
            archive.writestr(
                f"platform_{cutoff.strftime('%Y%m%d_%H%M')}.jsonl",
                "\n".join(platform_rows) + ("\n" if platform_rows else ""),
            )
        self._truncate_logs(self._audit_log_file, cutoff)
        self._truncate_logs(self._platform_log_file, cutoff)
        self._write_state(cutoff)
        result = LogBackupResult(
            zip_path=zip_path,
            audit_lines=len(audit_rows),
            platform_lines=len(platform_rows),
            cutoff_utc=cutoff,
        )
        if self._audit_logger is not None:
            self._audit_logger.emit(
                action="logs_backup_created",
                actor=actor,
                target="platform.logs",
                result="ok",
                reason=json.dumps(
                    {
                        "zip_path": str(zip_path),
                        "audit_lines": result.audit_lines,
                        "platform_lines": result.platform_lines,
                    },
                    ensure_ascii=True,
                ),
            )
        return result

    def get_last_backup_utc(self) -> datetime | None:
        if not self._state_file.exists():
            return None
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
            raw = payload.get("last_backup_utc")
            if not raw:
                return None
            parsed = datetime.fromisoformat(str(raw))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    def days_since_last_backup(self) -> int | None:
        last = self.get_last_backup_utc()
        if last is None:
            return None
        now = datetime.now(timezone.utc)
        return max((now - last).days, 0)

    def _write_state(self, cutoff: datetime) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps({"last_backup_utc": cutoff.astimezone(timezone.utc).isoformat()}, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _timestamp_from_json_line(line: str) -> datetime | None:
        try:
            parsed = json.loads(line)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        raw = parsed.get("timestamp_utc")
        if raw is None:
            return None
        try:
            value = datetime.fromisoformat(str(raw))
        except Exception:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _read_since(self, path: Path, previous_cutoff: datetime | None, cutoff: datetime) -> list[str]:
        if not path.exists():
            return []
        rows: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            ts = self._timestamp_from_json_line(line)
            if ts is None:
                continue
            if previous_cutoff is not None and ts <= previous_cutoff:
                continue
            if ts > cutoff:
                continue
            rows.append(line)
        return rows

    def _truncate_logs(self, path: Path, cutoff: datetime) -> None:
        if not path.exists():
            return
        keep_rows: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            ts = self._timestamp_from_json_line(line)
            if ts is None:
                continue
            if ts > cutoff:
                keep_rows.append(line)
        path.write_text("\n".join(keep_rows) + ("\n" if keep_rows else ""), encoding="utf-8")
