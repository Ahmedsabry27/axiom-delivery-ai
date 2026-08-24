"""Bounded JSON Schema 2020-12 subset used by Tool SDK inputs and outputs."""

from copy import deepcopy

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from app.tool_sdk.errors import InvalidToolInputError, OutputValidationError


def validate_and_default(schema: dict, value, *, output=False):
    data = deepcopy(value)
    errors: list[dict[str, str]] = []
    _validate(schema, data, "$", errors, apply_defaults=not output)
    for error in Draft202012Validator(schema).iter_errors(data):
        field = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        item = {"field": field, "message": error.message}
        if item not in errors:
            errors.append(item)
    if errors:
        cls = OutputValidationError if output else InvalidToolInputError
        raise cls(
            "Tool parameters did not match the declared schema"
            if not output
            else "Tool output did not match the declared schema",
            fields=errors,
        )
    return data


def _validate(schema, value, path, errors, apply_defaults=False):
    expected = schema.get("type")
    checks = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }
    if expected in checks and (
        not isinstance(value, checks[expected])
        or expected == "integer"
        and isinstance(value, bool)
    ):
        errors.append({"field": path, "message": f"must be {expected}"})
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append({"field": path, "message": "must be an allowed value"})
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key, definition in props.items():
            if key not in value and apply_defaults and "default" in definition:
                value[key] = deepcopy(definition["default"])
        for key in schema.get("required", []):
            if key not in value:
                errors.append({"field": f"{path}.{key}", "message": "is required"})
        if schema.get("additionalProperties") is False:
            for key in value.keys() - props.keys():
                errors.append({"field": f"{path}.{key}", "message": "is not allowed"})
        for key, child in value.items():
            if key in props:
                _validate(props[key], child, f"{path}.{key}", errors, apply_defaults)
    elif isinstance(value, list):
        if len(value) > schema.get("maxItems", 1000):
            errors.append({"field": path, "message": "has too many items"})
        for i, child in enumerate(value):
            _validate(
                schema.get("items", {}), child, f"{path}[{i}]", errors, apply_defaults
            )
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append({"field": path, "message": "is too short"})
        if len(value) > schema.get("maxLength", 10000):
            errors.append({"field": path, "message": "is too long"})
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", value):
            errors.append({"field": path, "message": "is below minimum"})
        if value > schema.get("maximum", value):
            errors.append({"field": path, "message": "is above maximum"})
