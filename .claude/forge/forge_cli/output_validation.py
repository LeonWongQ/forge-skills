# -*- coding: utf-8 -*-
"""Template-bound structured output schema resolution and validation."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
except ImportError:
    jsonschema = None

from .helpers import load_json_file_safe
from .registry_discovery import validate_instance_with_schema


OUTPUT_REGISTRY_PATH = Path("registry") / "template-outputs.json"


def _error(code: str, message: str, **details: Any) -> Dict[str, Any]:
    result = {"code": code, "message": message}
    if details:
        result["details"] = details
    return result


def _resolve_inside_root(root: Path, path_value: str) -> Tuple[Path | None, Dict[str, Any] | None]:
    candidate = (root / path_value.replace("\\", "/")).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None, _error(
            "OUTPUT_SCHEMA_PATH_ESCAPE",
            f"Registered output schema path escapes Forge root: {path_value}",
            schema_path=path_value,
        )
    return candidate, None


def resolve_template_output_schema(root: Path, template_id: str) -> Tuple[Path | None, List[Dict[str, Any]]]:
    """Resolve one canonical template ID to its registered output schema."""
    registry_path = root / OUTPUT_REGISTRY_PATH
    registry, error = load_json_file_safe(registry_path)
    if error:
        return None, [_error("OUTPUT_REGISTRY_INVALID", f"Cannot load output registry: {registry_path}", error=error)]
    if not isinstance(registry, dict):
        return None, [_error("OUTPUT_REGISTRY_INVALID", "Output registry must be a JSON object")]

    bindings = registry.get("template_outputs")
    if not isinstance(bindings, list):
        return None, [_error("OUTPUT_REGISTRY_INVALID", "Output registry missing valid 'template_outputs' list")]

    matches = [
        binding for binding in bindings
        if isinstance(binding, dict) and binding.get("template_id") == template_id
    ]
    if not matches:
        return None, [_error("OUTPUT_TEMPLATE_UNKNOWN", f"No output schema registered for template: {template_id}")]
    if len(matches) > 1:
        return None, [_error("OUTPUT_TEMPLATE_DUPLICATE", f"Multiple output schemas registered for template: {template_id}")]

    schema_value = matches[0].get("schema")
    if not isinstance(schema_value, str) or not schema_value:
        return None, [_error("OUTPUT_SCHEMA_INVALID_BINDING", f"Template binding has no valid schema path: {template_id}")]

    schema_path, path_error = _resolve_inside_root(root, schema_value)
    if path_error:
        return None, [path_error]
    if not schema_path.exists():
        return None, [_error(
            "OUTPUT_SCHEMA_MISSING",
            f"Registered output schema does not exist: {schema_value}",
            schema_path=schema_value,
        )]
    return schema_path, []


def validate_template_document(root: Path, template_id: str, document: Any) -> Dict[str, Any]:
    """Validate an in-memory JSON-compatible document against a template contract."""
    payload: Dict[str, Any] = {
        "command": "validate-output",
        "template_id": template_id,
        "schema_path": None,
        "valid": False,
        "errors": [],
    }
    schema_path, resolution_errors = resolve_template_output_schema(root, template_id)
    if resolution_errors:
        payload["errors"] = resolution_errors
        return payload

    payload["schema_path"] = str(schema_path.relative_to(root.resolve())).replace("\\", "/")
    schema, schema_error = load_json_file_safe(schema_path)
    if schema_error:
        payload["errors"] = [_error("OUTPUT_SCHEMA_INVALID_JSON", f"Cannot load output schema: {schema_path}", error=schema_error)]
        return payload
    if not isinstance(schema, dict):
        payload["errors"] = [_error("OUTPUT_SCHEMA_INVALID", f"Output schema must be a JSON object: {schema_path}")]
        return payload
    if jsonschema is None:
        payload["errors"] = [_error("JSONSCHEMA_NOT_INSTALLED", "jsonschema is required for output validation")]
        return payload

    errors = validate_instance_with_schema(document, schema)
    payload["errors"] = sorted(
        errors,
        key=lambda item: (item.get("path", "$"), item.get("schema_path", "$"), item.get("message", "")),
    )
    payload["valid"] = not payload["errors"]
    return payload


def validate_template_output(root: Path, template_id: str, input_path: Path) -> Dict[str, Any]:
    """Validate an already-structured JSON document against a template contract."""
    document, input_error = load_json_file_safe(input_path)
    if input_error:
        return {
            "command": "validate-output",
            "template_id": template_id,
            "input_path": str(input_path),
            "schema_path": None,
            "valid": False,
            "errors": [_error("OUTPUT_INPUT_INVALID_JSON", f"Cannot load input JSON: {input_path}", error=input_error)],
        }
    payload = validate_template_document(root, template_id, document)
    payload["input_path"] = str(input_path)
    return payload
