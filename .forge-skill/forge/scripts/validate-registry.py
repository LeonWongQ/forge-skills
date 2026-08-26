"""
validate-registry.py — Validate JSON format and schema compliance of all registry files.

Usage:
  python validate-registry.py
"""

import sys
import logging
from pathlib import Path
from jsonschema import validate, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import FORGE_ROOT, load_json, setup_logging, OK, FAIL

REGISTRY_DIR = FORGE_ROOT / "registry"
SCHEMA_DIR = REGISTRY_DIR / "schemas"

# Validate ALL registry-level files against their schemas (mirrors forge.py's
# REGISTRY_SCHEMA_CANDIDATES). Individual pack files are handled by
# validate-packs.py.  engine.json is intentionally absent — it does not exist
# on disk (engine modules are defined inside modules.json layers).
REGISTRY_SCHEMA_MAP = {
    "behaviors.json":           SCHEMA_DIR / "behaviors.schema.json",
    "checklists.json":          SCHEMA_DIR / "checklists.schema.json",
    "compositions.json":        SCHEMA_DIR / "compositions.schema.json",
    "contracts.json":           SCHEMA_DIR / "contracts.schema.json",
    "domains.json":             SCHEMA_DIR / "domains.schema.json",
    "modules.json":             SCHEMA_DIR / "modules.schema.json",
    "packs.json":               SCHEMA_DIR / "packs-index.schema.json",
    "project.json":             SCHEMA_DIR / "project.schema.json",
    "reports.json":             SCHEMA_DIR / "reports.schema.json",
    "route-regression.json":    SCHEMA_DIR / "route-regression.schema.json",
    "skill-routing.json":       SCHEMA_DIR / "skill-routing.schema.json",
    "skills.json":              SCHEMA_DIR / "skills.schema.json",
    "template-outputs.json":    SCHEMA_DIR / "template-outputs.schema.json",
    "templates.json":           SCHEMA_DIR / "templates.schema.json",
    "workflows.json":           SCHEMA_DIR / "workflows.schema.json",
}


def validate_one(reg_name: str, schema_path: Path) -> int:
    reg_path = REGISTRY_DIR / reg_name
    reg_data = load_json(reg_path)
    if reg_data is None:
        return 1
    schema_data = load_json(schema_path)
    if schema_data is None:
        return 1
    try:
        validate(instance=reg_data, schema=schema_data)
        print(f"  [{OK}] {reg_name} passes schema validation")
        return 0
    except ValidationError as e:
        print(f"  [{FAIL}] {reg_name}: schema violation — {e.message}")
        return 1


def validate_all_json_syntax() -> int:
    errors = 0
    for p in sorted(REGISTRY_DIR.glob("*.json")):
        data = load_json(p)
        if data is None:
            errors += 1
        else:
            print(f"  [{OK}] {p.name} — valid JSON")
    return errors


def main() -> int:
    setup_logging()
    log = logging.getLogger("validate-registry")
    log.debug("starting validation")
    print("=== validate-registry ===")
    print()
    print("[1/2] JSON syntax check (all registry/*.json)")
    errors = validate_all_json_syntax()
    print()
    print("[2/2] Schema validation (registry → schema)")
    for reg_name, schema_path in REGISTRY_SCHEMA_MAP.items():
        errors += validate_one(reg_name, schema_path)
    print()
    if errors:
        print(f"{FAIL} {errors} validation error(s).")
    else:
        print(f"{OK} All registry files valid.")
    return min(errors, 1)


if __name__ == "__main__":
    sys.exit(main())
