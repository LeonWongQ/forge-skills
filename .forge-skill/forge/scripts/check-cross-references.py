"""
check-cross-references.py — Verify id-based cross-references across all registry files are consistent.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import FORGE_ROOT, load_json, collect_ids, setup_logging, OK, FAIL

REGISTRY_DIR = FORGE_ROOT / "registry"


def known_ids() -> dict[str, dict]:
    merged = {}
    for reg_file, key in [
        ("modules.json", "layers"),
        ("behaviors.json", "behaviors"),
        ("templates.json", "templates"),
        ("checklists.json", "checklists"),
        ("workflows.json", "workflows"),
        ("packs.json", "packs"),
        ("skills.json", "skills"),
        ("reports.json", "reports"),
    ]:
        data = load_json(REGISTRY_DIR / reg_file)
        if data:
            merged.update(collect_ids(data, key))
    return merged


def check_entry_refs(entry: dict, known: dict[str, dict], source: str) -> int:
    errors = 0
    for field in ["primary_behavior", "behavior", "template", "default_template",
                   "workflow", "report_artifact"]:
        ref = entry.get(field)
        if ref and ref not in known:
            print(f"  [{FAIL}] {source}.{field} → '{ref}' not found")
            errors += 1
    for field in ["secondary_behaviors", "domains", "checklists", "default_checklists"]:
        for r in entry.get(field, []):
            if r not in known:
                print(f"  [{FAIL}] {source}.{field} → '{r}' not found")
                errors += 1
    for stage in entry.get("stages", []):
        if stage not in known:
            print(f"  [{FAIL}] {source}.stages → '{stage}' not found")
            errors += 1
    return errors


def check_references(known: dict[str, dict]) -> int:
    errors = 0
    comps = load_json(REGISTRY_DIR / "compositions.json")
    if comps:
        for comp in comps.get("compositions", []):
            errors += check_entry_refs(comp, known, f"compositions/{comp['id']}")
    # Workflows declare a `stages` field referencing engine.* ids in
    # modules.json. check_entry_refs already handles `stages`, but workflows
    # were never passed to it — so dangling engine.* stage refs went unflagged.
    workflows = load_json(REGISTRY_DIR / "workflows.json")
    if workflows:
        for wf in workflows.get("workflows", []):
            errors += check_entry_refs(wf, known, f"workflow:{wf['id']}")
    # Packs are validated for references by check-pack-references.py
    # (which understands the nested modules.behaviors / modules.domains structure).
    # We skip pack-level validation here to avoid false negatives.
    skills = load_json(REGISTRY_DIR / "skills.json")
    if skills:
        for skill in skills.get("skills", []):
            errors += check_entry_refs(skill, known, f"skill:{skill['id']}")
            for variant in skill.get("variants", []):
                errors += check_entry_refs(variant, known, f"skill:{skill['id']}/variant:{variant.get('type')}")
    return errors


def main() -> int:
    setup_logging()
    log = logging.getLogger("check-xref")
    log.debug("starting cross-reference check")
    print("=== check-cross-references ===")
    print("Building id map from all registry files...")
    known = known_ids()
    print(f"  {len(known)} known ids")
    print()
    print("Checking cross-references...")
    errors = check_references(known)
    print()
    if errors:
        print(f"{FAIL} {errors} dangling reference(s).")
    else:
        print(f"{OK} All cross-references valid.")
    return min(errors, 1)


if __name__ == "__main__":
    sys.exit(main())
