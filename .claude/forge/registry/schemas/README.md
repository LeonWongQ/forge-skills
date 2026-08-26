# Registry Schemas

## Purpose

This directory contains JSON Schema files for validating the machine-readable layer of Forge.

Schemas enforce local document structure and naming conventions. They are one layer of the broader validation system; the CLI combines them with path, cross-reference, pack, semantic, output-binding, and contract-fixture checks.

---

## Current Schemas

### Registry schemas

`modules.schema.json`, `skills.schema.json`, `workflows.schema.json`, `compositions.schema.json`, `skill-routing.schema.json`, and the layer/index schemas validate the registered JSON documents' shapes, identifiers, and required fields.

### Runtime and output schemas

- `runtime-state.schema.json` validates persisted runtime state representation.
- `template-*-output.schema.json` files validate supplied JSON against the output schema bound to a canonical template.
- `packs.schema.json`, `template-outputs.schema.json`, `contracts.schema.json`, and `route-regression.schema.json` validate their respective registry documents.

---

## Validation Layers

Run the complete seven-check set with:

```bash
python -m forge_cli --root . validate
```

| Check | Responsibility |
|-------|----------------|
| `registry` | JSON syntax and JSON Schema compliance for every registered registry document |
| `paths` | Registered paths exist and remain contained within the workspace |
| `refs` | Cross-file references between skills, workflows, compositions, and modules resolve |
| `packs` / `pack-refs` | Pack documents conform to schema and reference known IDs |
| `semantics` | Deterministic cross-registry, composition, routing, and template-binding invariants hold |
| `contracts` | Explicitly registered baseline/current API or event JSON Schema fixtures pass their required directions |

JSON Schema alone does **not** prove cross-file validity or domain-level semantics. The CLI layers above provide those deterministic checks.

### Contract validation boundary

The `contracts` check establishes only that explicitly registered fixtures are accepted or rejected by the configured schemas in the declared directions. It does not prove runtime delivery, consumer rollout, ordering, idempotency, rollback, or general schema-diff compatibility.

---

## Future Additions

Future improvements may include automatic registry generation, broader semantic analysis, and generalized schema-diff compatibility inference. Keep schemas focused on stable structural contracts and put cross-file or behavioral rules in the appropriate validation layer.

---

## Short Reminder

Schemas validate structure; the complete local quality gate validates the wider system contract.
