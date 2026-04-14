from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.migration_gates_documents import evaluate_registry_drift


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _expected_registry_state(status: str | None) -> tuple[str, bool]:
    if status == "APPROVED":
        return ("VALID", True)
    if status == "IN_REVIEW":
        return ("IN_REVIEW", True)
    if status == "IN_PROGRESS":
        return ("IN_PROGRESS", True)
    if status == "ARCHIVED":
        return ("ARCHIVED", False)
    return ("INVALID", True)


def rebuild_registry_from_documents(*, documents_db_path: Path, rebuilt_registry_db_path: Path) -> None:
    schema = Path("modules/registry/schema.sql").read_text(encoding="utf-8")
    rebuilt_registry_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(rebuilt_registry_db_path) as reg_conn:
        reg_conn.executescript(schema)
        reg_conn.execute("DELETE FROM document_registry")
        reg_conn.commit()

    with sqlite3.connect(documents_db_path) as docs_conn:
        doc_ids = [
            str(row[0])
            for row in docs_conn.execute(
                "SELECT document_id FROM document_headers ORDER BY document_id ASC"
            ).fetchall()
        ]
        versions = docs_conn.execute(
            """
            SELECT document_id, version, status
            FROM document_versions
            ORDER BY document_id ASC, version ASC
            """
        ).fetchall()

    status_by_doc: dict[str, list[tuple[int, str]]] = {}
    for document_id, version, status in versions:
        status_by_doc.setdefault(str(document_id), []).append((int(version), str(status)))

    with sqlite3.connect(rebuilt_registry_db_path) as reg_conn:
        for doc_id in doc_ids:
            rows = status_by_doc.get(doc_id, [])
            approved_versions = [version for version, status in rows if status == "APPROVED"]
            active_version = max(approved_versions) if approved_versions else None
            status_basis = "APPROVED" if active_version is not None else (rows[-1][1] if rows else None)
            register_state, is_findable = _expected_registry_state(status_basis)
            reg_conn.execute(
                """
                INSERT INTO document_registry (
                    document_id, active_version, release_note, release_evidence_mode,
                    register_state, is_findable, valid_from, valid_until,
                    last_update_event_id, last_update_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    active_version,
                    None,
                    "WORKFLOW",
                    register_state,
                    1 if is_findable else 0,
                    None,
                    None,
                    f"recovery-drill:{doc_id}",
                    _now_iso(),
                ),
            )
        reg_conn.commit()


def run_recovery_drill(*, documents_db_path: Path, registry_db_path: Path, evidence_dir: Path, rebuilt_registry_db_path: Path) -> dict[str, object]:
    started_at = _now_iso()
    before = evaluate_registry_drift(documents_db_path=documents_db_path, registry_db_path=registry_db_path)
    rebuild_registry_from_documents(
        documents_db_path=documents_db_path,
        rebuilt_registry_db_path=rebuilt_registry_db_path,
    )
    after = evaluate_registry_drift(
        documents_db_path=documents_db_path,
        registry_db_path=rebuilt_registry_db_path,
    )
    finished_at = _now_iso()
    payload: dict[str, object] = {
        "ok": bool(after["ok"]),
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "documents_db_path": str(documents_db_path),
        "source_registry_db_path": str(registry_db_path),
        "rebuilt_registry_db_path": str(rebuilt_registry_db_path),
        "drift_before": before,
        "drift_after_rebuild": after,
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "registry_recovery_drill_evidence.json"
    evidence_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    payload["evidence_file"] = str(evidence_file)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run registry recovery drill and emit evidence")
    parser.add_argument("--documents-db-path", required=True)
    parser.add_argument("--registry-db-path", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--rebuilt-registry-db-path", required=True)
    args = parser.parse_args()

    payload = run_recovery_drill(
        documents_db_path=Path(args.documents_db_path),
        registry_db_path=Path(args.registry_db_path),
        evidence_dir=Path(args.evidence_dir),
        rebuilt_registry_db_path=Path(args.rebuilt_registry_db_path),
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if bool(payload["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
