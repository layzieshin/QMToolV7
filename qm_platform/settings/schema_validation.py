"""JSON-Schema subset validator for module settings contributions (no external dep)."""

from __future__ import annotations

from typing import Any, Mapping

from qm_platform.settings.errors import SettingsSchemaInvalidError
from qm_platform.settings.key_classification import SettingBucket, classify_key


def technical_settings_schema(module_id: str, contribution_schema: Mapping[str, Any]) -> dict[str, Any]:
    """Project a contribution schema onto Bucket-B keys only."""
    props = contribution_schema.get("properties") or {}
    if not isinstance(props, Mapping):
        raise SettingsSchemaInvalidError("settings schema properties must be an object")
    technical_props = {
        str(key): value
        for key, value in props.items()
        if classify_key(module_id, str(key)) is SettingBucket.TECHNICAL
    }
    required = [
        str(key)
        for key in (contribution_schema.get("required") or [])
        if classify_key(module_id, str(key)) is SettingBucket.TECHNICAL
    ]
    return {
        "type": "object",
        "properties": technical_props,
        "required": required,
        "additionalProperties": False,
    }


def validate_against_schema(value: Any, schema: Mapping[str, Any], *, path: str = "$") -> None:
    """Validate ``value`` against a JSON-Schema subset used by settings contributions.

    Supported keywords: type, properties, required, additionalProperties, items,
    minimum, maximum, enum.
    """
    if not isinstance(schema, Mapping):
        raise SettingsSchemaInvalidError(f"schema at {path} must be an object")

    expected_type = schema.get("type")
    if expected_type is not None:
        _assert_type(value, str(expected_type), path=path)

    if "enum" in schema:
        allowed = schema.get("enum")
        if not isinstance(allowed, list):
            raise SettingsSchemaInvalidError(f"schema enum at {path} must be an array")
        if value not in allowed:
            raise SettingsSchemaInvalidError(f"value at {path} is not in enum")

    if expected_type == "integer" or (expected_type is None and isinstance(value, int) and not isinstance(value, bool)):
        if "minimum" in schema and isinstance(value, int) and not isinstance(value, bool):
            if value < schema["minimum"]:
                raise SettingsSchemaInvalidError(
                    f"value at {path} is below minimum {schema['minimum']}"
                )
        if "maximum" in schema and isinstance(value, int) and not isinstance(value, bool):
            if value > schema["maximum"]:
                raise SettingsSchemaInvalidError(
                    f"value at {path} is above maximum {schema['maximum']}"
                )

    if expected_type == "number" or (
        expected_type is None and isinstance(value, (int, float)) and not isinstance(value, bool)
    ):
        if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < schema["minimum"]:
                raise SettingsSchemaInvalidError(
                    f"value at {path} is below minimum {schema['minimum']}"
                )
        if "maximum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool):
            if value > schema["maximum"]:
                raise SettingsSchemaInvalidError(
                    f"value at {path} is above maximum {schema['maximum']}"
                )

    if expected_type == "object" or (expected_type is None and isinstance(value, dict)):
        if not isinstance(value, dict):
            return
        props = schema.get("properties") or {}
        if not isinstance(props, Mapping):
            raise SettingsSchemaInvalidError(f"schema properties at {path} must be an object")
        required = schema.get("required") or []
        if not isinstance(required, list):
            raise SettingsSchemaInvalidError(f"schema required at {path} must be an array")
        for key in required:
            if str(key) not in value:
                raise SettingsSchemaInvalidError(f"missing required property {path}.{key}")
        additional = schema.get("additionalProperties", True)
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in props:
                child_schema = props[key]
                if not isinstance(child_schema, Mapping):
                    raise SettingsSchemaInvalidError(f"schema for {child_path} must be an object")
                validate_against_schema(child, child_schema, path=child_path)
                continue
            if additional is False:
                raise SettingsSchemaInvalidError(f"additional property not allowed: {child_path}")
            if isinstance(additional, Mapping):
                validate_against_schema(child, additional, path=child_path)

    if expected_type == "array" or (expected_type is None and isinstance(value, list)):
        if not isinstance(value, list):
            return
        items = schema.get("items")
        if items is None:
            return
        if not isinstance(items, Mapping):
            raise SettingsSchemaInvalidError(f"schema items at {path} must be an object")
        for index, child in enumerate(value):
            validate_against_schema(child, items, path=f"{path}[{index}]")


def validate_technical_settings_payload(
    module_id: str,
    values: Mapping[str, Any],
    contribution_schema: Mapping[str, Any],
) -> None:
    """Fail-closed schema validation for a complete Bucket-B payload."""
    schema = technical_settings_schema(module_id, contribution_schema)
    validate_against_schema(dict(values), schema, path=f"$.{module_id}")


def _assert_type(value: Any, expected: str, *, path: str) -> None:
    if expected == "string":
        ok = isinstance(value, str)
    elif expected == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected == "boolean":
        ok = isinstance(value, bool)
    elif expected == "array":
        ok = isinstance(value, list)
    elif expected == "object":
        ok = isinstance(value, dict)
    elif expected == "null":
        ok = value is None
    else:
        raise SettingsSchemaInvalidError(f"unsupported schema type {expected!r} at {path}")
    if not ok:
        raise SettingsSchemaInvalidError(
            f"value at {path} has invalid type (expected {expected})"
        )
