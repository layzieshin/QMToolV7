from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qm_platform.sdk.module_contract import SettingsContribution
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore
from scripts.migration_gates_documents import evaluate_gates, evaluate_registry_drift


def _has_text(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8")


def _governance_guard_enforced() -> bool:
    registry = SettingsRegistry()
    registry.register(
        SettingsContribution(
            module_id="usermanagement",
            schema_version=1,
            schema={"type": "object"},
            defaults={"seed_mode": "legacy_defaults"},
            scope="module_global",
            migrations=[],
        )
    )
    with tempfile.TemporaryDirectory() as tmp:
        service = SettingsService(registry=registry, store=SettingsStore(Path(tmp) / "settings.json"))
        try:
            service.set_module_settings("usermanagement", {"seed_mode": "hardened"})
        except ValueError:
            return True
        return False


def evaluate_golive_gate(*, documents_db_path: Path | None, registry_db_path: Path | None, baseline_other_count: int | None) -> dict[str, object]:
    ci_workflow_path = Path(".github/workflows/ci-gates.yml")
    checks: dict[str, bool] = {
        "ci_workflow_present": ci_workflow_path.exists(),
        "license_generator_present": Path("scripts/license_generate.py").exists(),
        "recovery_drill_script_present": Path("scripts/registry_recovery_drill.py").exists(),
        "profile_coverage_guard_present": Path("tests/modules/test_documents_profile_coverage_guard.py").exists(),
        "central_governance_service_enforced": _governance_guard_enforced(),
        "production_seed_guard_present": _has_text(
            Path("modules/usermanagement/module.py"),
            "production profile requires usermanagement.seed_mode='hardened'",
        ),
    }

    diagnostics: dict[str, object] = {}
    if not checks["ci_workflow_present"]:
        diagnostics["ci_workflow_present"] = {
            "path": str(ci_workflow_path),
            "hint": "missing archive content or checkout excludes .github/workflows",
        }
    if documents_db_path is not None:
        gate = evaluate_gates(
            documents_db_path=documents_db_path,
            profiles_path=Path("modules/documents/workflow_profiles.json"),
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
