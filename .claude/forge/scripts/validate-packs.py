"""
validate-packs.py — Validate each individual pack JSON file against packs.schema.json.

Usage:
  python validate-packs.py
"""

import sys
import logging
from pathlib import Path
from jsonschema import validate, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import FORGE_ROOT, load_json, setup_logging, OK, FAIL

PACKS_INDEX = FORGE_ROOT / "registry" / "packs.json"
PACK_SCHEMA = FORGE_ROOT / "registry" / "schemas" / "packs.schema.json"


def validate_pack(pack_file: Path, schema: dict) -> int:
    """Validate one pack JSON against the pack schema."""
    data = load_json(pack_file)
    if data is None:
        return 1
    pid = data.get("id", pack_file.stem)
    try:
        validate(instance=data, schema=schema)
        print(f"  [{OK}] {pid}")
        return 0
    except ValidationError as e:
        print(f"  [{FAIL}] {pid}: {e.message}")
        return 1


def main() -> int:
    setup_logging()
    log = logging.getLogger("validate-packs")
    log.debug("starting pack validation")
    print("=== validate-packs ===")
    print()

    schema = load_json(PACK_SCHEMA)
    if schema is None:
        return 1

    packs_index = load_json(PACKS_INDEX)
    if packs_index is None:
        return 1

    errors = 0
    for pack in packs_index.get("packs", []):
        pack_path = FORGE_ROOT / pack.get("path", "")
        errors += validate_pack(pack_path, schema)

    print()
    if errors:
        print(f"{FAIL} {errors} pack validation error(s).")
    else:
        print(f"{OK} All packs valid.")
    return min(errors, 1)


if __name__ == "__main__":
    sys.exit(main())
