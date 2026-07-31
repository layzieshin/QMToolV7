from __future__ import annotations

from scripts.database_migration_gate import evaluate_database_migration_gate


def test_database_migration_gate_is_green() -> None:
    payload = evaluate_database_migration_gate()

    assert payload["ok"] is True, payload
