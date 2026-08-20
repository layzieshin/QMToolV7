"""Export the deterministic J04-M0 HTTP contract.

The application remains the OpenAPI owner. This script only serializes the
application-generated schema and performs repository-safety checks before
writing the versioned contract artifact.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.api import (  # noqa: E402
    _DOCUMENTS_CREATE_FROM_TEMPLATE,
    _DOCUMENTS_IF_MATCH_REQUIRED,
    _DOCUMENTS_STATE_RESPONSE_SCHEMAS,
    create_app,
)


FORBIDDEN_MARKERS = (
    "QMTOOL_SESSION_TOKEN=",
    "QMTOOL_PG_PASSWORD=",
    "documents.db",
    "storage_key",
    "SQLite",
    "I:/Projekte/",
)


def _if_match_parameter(operation: dict[str, object]) -> dict[str, object] | None:
    for parameter in operation.get("parameters") or []:
        if isinstance(parameter, dict) and parameter.get("name") == "If-Match" and parameter.get("in") == "header":
            return parameter
    return None


def _validate_contract(document: dict[str, object]) -> None:
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise SystemExit("OpenAPI export contains no paths")
    operation_ids: list[str] = []
    required_if_match: set[tuple[str, str]] = set()
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            if not isinstance(operation, dict) or not operation.get("operationId"):
                raise SystemExit(f"missing operationId for {method.upper()} {path}")
            operation_ids.append(str(operation["operationId"]))
            if_match = _if_match_parameter(operation)
            if if_match is not None and if_match.get("required") is True:
                required_if_match.add((method, path))
                if "428" not in operation.get("responses", {}):
                    raise SystemExit(f"missing 428 for required If-Match operation {method.upper()} {path}")
    duplicates = sorted({item for item in operation_ids if operation_ids.count(item) > 1})
    if duplicates:
        raise SystemExit(f"duplicate operationIds: {duplicates}")
    if required_if_match != set(_DOCUMENTS_IF_MATCH_REQUIRED):
        missing = sorted(set(_DOCUMENTS_IF_MATCH_REQUIRED) - required_if_match)
        extra = sorted(required_if_match - set(_DOCUMENTS_IF_MATCH_REQUIRED))
        raise SystemExit(f"If-Match required set mismatch; missing={missing}; extra={extra}")

    create_method, create_path = _DOCUMENTS_CREATE_FROM_TEMPLATE
    create_op = paths.get(create_path, {}).get(create_method)
    if not isinstance(create_op, dict):
        raise SystemExit("create-from-template operation missing from OpenAPI")
    create_if_match = _if_match_parameter(create_op)
    if create_if_match is None or create_if_match.get("required") is not False:
        raise SystemExit("create-from-template must document optional If-Match")
    if "already exists" not in str(create_if_match.get("description", "")):
        raise SystemExit("create-from-template If-Match description must explain conditional requirement")
    if "428" not in create_op.get("responses", {}):
        raise SystemExit("create-from-template must document HTTP 428")

    schemas = document.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        raise SystemExit("OpenAPI export contains no schemas")
    for required in ("ErrorDetail", "ErrorResponse"):
        if required not in schemas:
            raise SystemExit(f"missing required schema: {required}")
    error_detail = schemas["ErrorDetail"]
    properties = error_detail.get("properties", {}) if isinstance(error_detail, dict) else {}
    if "current_state" not in properties:
        raise SystemExit("ErrorDetail must expose current_state")
    if "state" in properties:
        raise SystemExit("ErrorDetail must not expose internal state")
    for name in _DOCUMENTS_STATE_RESPONSE_SCHEMAS:
        model = schemas.get(name)
        if not isinstance(model, dict):
            raise SystemExit(f"missing response schema: {name}")
        required_fields = model.get("required") or []
        if "available_actions" not in required_fields:
            raise SystemExit(f"{name}.available_actions must be required")

    serialized = json.dumps(document, ensure_ascii=True, sort_keys=True)
    for marker in FORBIDDEN_MARKERS:
        if marker in serialized:
            raise SystemExit(f"forbidden internal or secret marker in OpenAPI: {marker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the J04-M0 OpenAPI contract")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "contracts" / "j04-m0-openapi.json",
    )
    args = parser.parse_args()
    document = create_app().openapi()
    _validate_contract(document)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
