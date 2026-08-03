from __future__ import annotations

from scripts.database_migration_gate import evaluate_database_migration_gate
from scripts import json_persistence_gate as jpg


def test_database_migration_gate_is_green() -> None:
    payload = evaluate_database_migration_gate()

    assert payload["ok"] is True, payload
    assert payload["checks"]["no_unregistered_json_persistence"] is True


def test_database_migration_gate_turns_red_on_json_persistence_finding(
    monkeypatch,
) -> None:
    def fake_evaluate(*_args, **_kwargs):
        return {
            "ok": False,
            "checks": {"no_unregistered_json_persistence": False},
            "findings": [
                {
                    "kind": "unregistered_domain_json_file",
                    "path": "modules/documents/evil.json",
                    "detail": "synthetic",
                    "classification": "new_unregistered",
                }
            ],
            "diagnostics": {"new_unregistered": ["modules/documents/evil.json"]},
        }

    monkeypatch.setattr(jpg, "evaluate_json_persistence_gate", fake_evaluate)
    # database_migration_gate imported the function by name — patch there too
    import scripts.database_migration_gate as dmg

    monkeypatch.setattr(dmg, "evaluate_json_persistence_gate", fake_evaluate)
    payload = evaluate_database_migration_gate()
    assert payload["ok"] is False
    assert payload["checks"]["no_unregistered_json_persistence"] is False
    assert "json_persistence" in payload["diagnostics"]
    assert payload["diagnostics"]["json_persistence"]["findings"]
