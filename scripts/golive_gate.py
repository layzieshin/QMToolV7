from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.sdk.module_contract import SettingsContribution
from qm_platform.settings.settings_registry import SettingsRegistry
from scripts.migration_gates_documents import evaluate_gates, evaluate_registry_drift
from scripts.database_migration_gate import evaluate_database_migration_gate


def _has_text(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8")


def _governance_guard_enforced() -> bool:
    from datetime import datetime, timezone

    from modules.usermanagement.contracts import issue_user_context
    from qm_platform.settings.testing import build_settings_service_for_tests

    contribution = SettingsContribution(
        module_id="usermanagement",
        schema_version=1,
        schema={
            "type": "object",
            "properties": {
                "seed_mode": {"type": "string"},
                "dev_mode": {"type": "boolean"},
            },
            "required": ["seed_mode", "dev_mode"],
            "additionalProperties": False,
        },
        defaults={"seed_mode": "legacy_defaults", "dev_mode": False},
        scope="module_global",
        migrations=[],
    )
    with tempfile.TemporaryDirectory() as tmp:
        service = build_settings_service_for_tests(Path(tmp))
        service.registry.register(contribution)
        actor = issue_user_context(
            user_id="u1",
            session_id="s1",
            request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
            username="admin",
            global_roles=["Admin"],
            is_qmb=False,
            authenticated_at=datetime.now(timezone.utc),
        )
        try:
            service.set_module_settings(
                "usermanagement",
                {"seed_mode": "hardened", "dev_mode": False},
                actor=actor,
            )
        except ValueError:
            return True
        return False


def evaluate_golive_gate(*, documents_db_path: Path | None, registry_db_path: Path | None, baseline_other_count: int | None) -> dict[str, object]:
    ci_workflow_path = Path(".github/workflows/ci-gates.yml")
    checks: dict[str, bool] = {
        "ci_workflow_present": ci_workflow_path.exists(),
        "internal_license_issuer_present": Path("tools/internal_license_issuer/create_license.py").exists(),
        "recovery_drill_script_present": Path("scripts/registry_recovery_drill.py").exists(),
        "profile_coverage_guard_present": Path("tests/modules/test_documents_profile_coverage_guard.py").exists(),
        "central_governance_service_enforced": _governance_guard_enforced(),
        "production_seed_guard_present": _has_text(
            Path("modules/usermanagement/module.py"),
            "production profile requires usermanagement.seed_mode",
        ),
    }

    diagnostics: dict[str, object] = {}
    database_gate = evaluate_database_migration_gate()
    diagnostics["database_migration_gate"] = database_gate
    checks["database_migration_foundation_ok"] = bool(database_gate["ok"])
    if not checks["ci_workflow_present"]:
        diagnostics["ci_workflow_present"] = {
            "path": str(ci_workflow_path),
            "hint": "missing archive content or checkout excludes .github/workflows",
        }
    if documents_db_path is not None:
        gate = evaluate_gates(
            documents_db_path=documents_db_path,
            baseline_other_count=baseline_other_count,
        )
        diagnostics["migration_gates"] = gate
        checks["migration_gates_ok"] = bool(gate["ok"])
    if documents_db_path is not None and registry_db_path is not None:
        drift = evaluate_registry_drift(
            documents_db_path=documents_db_path,
            registry_db_path=registry_db_path,
        )
        diagnostics["registry_drift"] = drift
        checks["registry_drift_ok"] = bool(drift["ok"])

    ok = all(checks.values())
    return {
        "ok": ok,
        "checks": checks,
        "diagnostics": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run consolidated Go-Live gate checks")
    parser.add_argument("--documents-db-path")
    parser.add_argument("--registry-db-path")
    parser.add_argument("--baseline-other-count", type=int)
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = evaluate_golive_gate(
        documents_db_path=Path(args.documents_db_path) if args.documents_db_path else None,
        registry_db_path=Path(args.registry_db_path) if args.registry_db_path else None,
        baseline_other_count=args.baseline_other_count,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if bool(payload["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
