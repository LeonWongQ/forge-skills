"""
check-pack-references.py — Verify pack references (behaviors, domains, templates,
checklists, workflows, reports) point to known ids in corresponding registries.

Packs use a nested "modules" structure: modules.behaviors, modules.domains, etc.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import FORGE_ROOT, load_json, collect_ids, setup_logging, OK, FAIL

REGISTRY_DIR = FORGE_ROOT / "registry"


def build_set(reg_file: str, key: str) -> set[str]:
    data = load_json(REGISTRY_DIR / reg_file)
    if data is None:
        return set()
    return set(collect_ids(data, key).keys())


def main() -> int:
    setup_logging()
    log = logging.getLogger("check-pack-refs")
    log.debug("starting pack reference check")
    print("=== check-pack-references ===")
    print()

    valid_behaviors = build_set("behaviors.json", "behaviors")
    domains_data = load_json(REGISTRY_DIR / "domains.json")
    if domains_data:
        valid_domains = set(collect_ids(domains_data, "domains").keys())
    else:
        valid_domains = set()
    valid_templates = build_set("templates.json", "templates")
    valid_checklists = build_set("checklists.json", "checklists")
    valid_workflows = build_set("workflows.json", "workflows")
    valid_reports = build_set("reports.json", "reports")

    print(f"  behaviors={len(valid_behaviors)}, domains={len(valid_domains)}, "
          f"templates={len(valid_templates)}, checklists={len(valid_checklists)}, "
          f"workflows={len(valid_workflows)}, reports={len(valid_reports)}")
    print()

    packs_index = load_json(REGISTRY_DIR / "packs.json")
    if packs_index is None:
        return 1

    total_errors = 0
    for pack in packs_index.get("packs", []):
        pack_data = load_json(FORGE_ROOT / pack.get("path", ""))
        if pack_data is None:
            total_errors += 1
            continue
        pid = pack_data.get("id", pack.get("id", "UNKNOWN"))
        mods = pack_data.get("modules", {})
        pack_errors = 0

        # behaviors from modules.behaviors
        for ref in mods.get("behaviors", []):
            if ref not in valid_behaviors:
                print(f"  [{FAIL}] {pid}.modules.behaviors → '{ref}' (not a known behavior)")
                pack_errors += 1

        # domains from modules.domains
        for ref in mods.get("domains", []):
            if ref not in valid_domains:
                print(f"  [{FAIL}] {pid}.modules.domains → '{ref}' (not a known domain)")
                pack_errors += 1

        # template (flat field)
        ref = pack_data.get("template")
        if ref and ref not in valid_templates:
            print(f"  [{FAIL}] {pid}.template → '{ref}' (not a known template)")
            pack_errors += 1

        # checklists (flat field)
        for ref in pack_data.get("checklists", []):
            if ref not in valid_checklists:
                print(f"  [{FAIL}] {pid}.checklists → '{ref}' (not a known checklist)")
                pack_errors += 1

        # workflow (flat field)
        ref = pack_data.get("workflow")
        if ref and ref not in valid_workflows:
            print(f"  [{FAIL}] {pid}.workflow → '{ref}' (not a known workflow)")
            pack_errors += 1

        # reports (flat field)
        for ref in pack_data.get("reports", []):
            if ref not in valid_reports:
                print(f"  [{FAIL}] {pid}.reports → '{ref}' (not a known report)")
                pack_errors += 1

        if pack_errors == 0:
            print(f"  [{OK}] {pid}")
        total_errors += pack_errors

    print()
    if total_errors:
        print(f"{FAIL} {total_errors} invalid reference(s).")
    else:
        print(f"{OK} All pack references valid.")
    return min(total_errors, 1)


if __name__ == "__main__":
    sys.exit(main())
