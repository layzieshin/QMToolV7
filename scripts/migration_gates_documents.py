from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


VALID_DOC_TYPES = ("VA", "AA", "FB", "LS", "EXT", "OTHER")
VALID_CONTROL_CLASSES = ("CONTROLLED", "CONTROLLED_SHORT", "EXTERNAL", "RECORD")


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


def _load_profiles(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = data.get("profiles", [])
    mapping: dict[str, str] = {}
    for row in profiles:
        profile_id = str(row.get("profile_id", "")).strip()
        control_class = str(row.get("control_class", "")).strip()
        if profile_id and control_class:
            mapping[profile_id] = control_class
    return mapping


def _count_invalid_headers(conn: sqlite3.Connection, profile_mapping: dict[str, str]) -> int:
    rows = conn.execute(
        """
        SELECT doc_type, control_class, workflow_profile_id
        FROM document_headers
        """
    ).fetchall()
    invalid = 0
    for doc_type, control_class, workflow_profile_id in rows:
        dt = str(doc_type)
        cc = str(control_class)
        pf = str(workflow_profile_id)
        if dt not in VALID_DOC_TYPES:
            invalid += 1
            continue
        if cc not in VALID_CONTROL_CLASSES:
            invalid += 1
            continue
        expected_class = profile_mapping.get(pf)
        if expected_class is None or expected_class != cc:
            invalid += 1
    return invalid


def _count_invalid_versions(conn: sqlite3.Connection, profile_mapping: dict[str, str]) -> int:
    rows = conn.execute(
        """
        SELECT doc_type, control_class, workflow_profile_id
        FROM document_versions
        """
    ).fetchall()
    invalid = 0
    for doc_type, control_class, workflow_profile_id in rows:
        dt = str(doc_type)
        cc = str(control_class)
        pf = str(workflow_profile_id)
        if dt not in VALID_DOC_TYPES:
            invalid += 1
            continue
        if cc not in VALID_CONTROL_CLASSES:
            invalid += 1
            continue
        expected_class = profile_mapping.get(pf)
        if expected_class is None or expected_class != cc:
            invalid += 1
    return invalid


def evaluate_gates(
    *,
    documents_db_path: Path,
    profiles_path: Path,
    baseline_other_count: int | None,
) -> dict[str, object]:
    profile_mapping = _load_profiles(profiles_path)
    with sqlite3.connect(documents_db_path) as conn:
        other_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM document_headers WHERE doc_type = 'OTHER'"
            ).fetchone()[0]
        )
        invalid_headers = _count_invalid_headers(conn, profile_mapping)
        invalid_versions = _count_invalid_versions(conn, profile_mapping)

    invalid_total = invalid_headers + invalid_versions
    gate_other_not_increased = baseline_other_count is None or other_count <= baseline_other_count
    gate_no_invalid_combinations = invalid_total == 0
    ok = gate_other_not_increased and gate_no_invalid_combinations
    return {
        "ok": ok,
        "documents_db_path": str(documents_db_path),
        "profiles_path": str(profiles_path),
        "metrics": {
            "doc_type_other_count": other_count,
            "invalid_header_combinations": invalid_headers,
            "invalid_version_combinations": invalid_versions,
            "invalid_total": invalid_total,
        },
        "gates": {
            "other_not_increased": {
                "ok": gate_other_not_increased,
                "baseline_other_count": baseline_other_count,
                "current_other_count": other_count,
            },
            "invalid_combinations_zero": {
                "ok": gate_no_invalid_combinations,
                "current_invalid_total": invalid_total,
            },
        },
    }


def evaluate_registry_drift(*, documents_db_path: Path, registry_db_path: Path) -> dict[str, object]:
    with sqlite3.connect(documents_db_path) as docs_conn:
        header_ids = {
            str(row[0])
            for row in docs_conn.execute(
                "SELECT document_id FROM document_headers"
            ).fetchall()
        }
        approved_versions = {
            str(document_id): int(version)
            for document_id, version in docs_conn.execute(
                "SELECT document_id, version FROM document_versions WHERE status = 'APPROVED'"
            ).fetchall()
        }
        latest_versions = {
            str(document_id): int(version)
            for document_id, version in docs_conn.execute(
                "SELECT document_id, MAX(version) FROM document_versions GROUP BY document_id"
            ).fetchall()
        }
        status_rows = docs_conn.execute(
            "SELECT document_id, version, status FROM document_versions"
        ).fetchall()
    status_by_doc_version = {
        (str(document_id), int(version)): str(status)
        for document_id, version, status in status_rows
    }
    latest_status_by_doc: dict[str, str] = {}
    for doc_id, latest_version in latest_versions.items():
        status = status_by_doc_version.get((doc_id, latest_version))
        if status is not None:
            latest_status_by_doc[doc_id] = status

    with sqlite3.connect(registry_db_path) as reg_conn:
        registry_rows = reg_conn.execute(
            """
            SELECT document_id, active_version, register_state, is_findable
            FROM document_registry
            """
        ).fetchall()

    registry_by_doc = {
        str(document_id): {
            "active_version": int(active_version) if active_version is not None else None,
            "register_state": str(register_state),
            "is_findable": bool(is_findable),
        }
        for document_id, active_version, register_state, is_findable in registry_rows
    }

    missing_registry_entries = len(header_ids - set(registry_by_doc.keys()))
    active_version_mismatch = 0
    state_mismatch = 0
    for doc_id in header_ids:
        reg = registry_by_doc.get(doc_id)
        if reg is None:
            continue
        expected_active = approved_versions.get(doc_id)
        if reg["active_version"] != expected_active:
            active_version_mismatch += 1

        status_basis: str | None
        if reg["active_version"] is not None:
            status_basis = status_by_doc_version.get((doc_id, int(reg["active_version"])))
        else:
            status_basis = latest_status_by_doc.get(doc_id)
        expected_state, expected_findable = _expected_registry_state(status_basis)
        if reg["register_state"] != expected_state or bool(reg["is_findable"]) != bool(expected_findable):
            state_mismatch += 1

    drift_total = missing_registry_entries + active_version_mismatch + state_mismatch
    return {
        "ok": drift_total == 0,
        "documents_db_path": str(documents_db_path),
        "registry_db_path": str(registry_db_path),
        "metrics": {
            "missing_registry_entries": missing_registry_entries,
            "active_version_mismatch": active_version_mismatch,
            "state_mismatch": state_mismatch,
            "drift_total": drift_total,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Documents migration gate checks")
    parser.add_argument("--documents-db-path", required=True)
    parser.add_argument("--profiles-path", default="modules/documents/workflow_profiles.json")
    parser.add_argument(
        "--registry-db-path",
        help="Optional registry DB path to run drift checks from architecture contract",
    )
    parser.add_argument(
        "--baseline-other-count",
        type=int,
        help="Pre-migration baseline for doc_type=OTHER; gate fails if current count is higher",
    )
    args = parser.parse_args()

    payload = evaluate_gates(
        documents_db_path=Path(args.documents_db_path),
        profiles_path=Path(args.profiles_path),
        baseline_other_count=args.baseline_other_count,
    )
    if args.registry_db_path:
        payload["registry_drift"] = evaluate_registry_drift(
            documents_db_path=Path(args.documents_db_path),
            registry_db_path=Path(args.registry_db_path),
        )
        payload["ok"] = bool(payload["ok"]) and bool(payload["registry_drift"]["ok"])
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if bool(payload["ok"]) else 2


if __name__ == "__main__":
    sys.exit(main())
