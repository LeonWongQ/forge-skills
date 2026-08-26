# Registry

## Purpose

This directory contains machine-readable metadata for the repository.

The registry exists to support:
- programmatic module discovery
- task routing
- composition selection
- template selection
- checklist selection
- runtime integration
- deterministic validation tooling

The registry is not the source of architectural truth.
The markdown modules remain the source of behavioral truth.
The registry is a machine-readable index and routing layer.

---

## Design Principles

Registry files should be:

- simple
- explicit
- stable
- easy to parse
- low-duplication
- vendor-neutral

They should help a runtime answer:
- what modules exist
- what layer they belong to
- when they are likely relevant
- how compositions should be assembled

---

## Files

### `modules.json`
Canonical inventory of major modules grouped by layer.

Use it to answer:
- what files exist
- what their ids are
- what path to load

### `behaviors.json`
Behavior routing metadata.

Use it to answer:
- which behavior fits a task
- what keywords suggest that behavior
- what template/checklists are commonly paired with it

### `domains.json`
Domain routing metadata.

Use it to answer:
- which technical domain is relevant
- what signals suggest activating that domain
- which other domains commonly pair with it

### `templates.json`
Template inventory and selection metadata.

Use it to answer:
- what templates exist
- what each template is best for

### `template-outputs.json`
Structured output schema bindings for templates.

Use it to answer:
- which JSON Schema should validate output for a given template

### How `templates.json` and `template-outputs.json` differ

These files are related but not interchangeable:
- `templates.json` is for template discovery and selection
- `template-outputs.json` is for output contract resolution

### `checklists.json`
Checklist selection metadata.

Use it to answer:
- what quality gates should be applied
- which checklist is associated with which task mode

### `reports.json`
Persistent artifact metadata.

Use it to answer:
- which report artifact best fits a reusable outcome

### `workflows.json`
**Single authority** for workflow path definitions.

All workflow paths are defined here using the `workflow.*` id namespace.

Use it to answer:
- what the default workflow path is
- what named lighter/heavier workflow paths exist

The legacy `engine.json` file is deprecated and should not be used as a workflow source.

### `compositions.json`
Predefined common task compositions.

Use it to answer:
- which ready-made composition best matches a task pattern

---

## Recommended Responsibilities

To avoid duplication, use the following role split:

### `modules.json`
Acts as the canonical inventory of module ids and paths.

**Scope note:** The module registry is not a full repository file index.

It intentionally focuses on runtime-relevant and composition-relevant modules:
- kernel
- engine
- runtime
- behaviors
- domains
- templates
- checklists
- reports

General documentation, standards, onboarding material, packs, scripts, and integration guides are managed by their own registries or are not required to appear in `modules.json`.

### Other registry files
Add selection metadata and routing hints, but should avoid redefining basic path inventory if possible.

If duplication becomes too high, prefer:
- `modules.json` as source of module identity
- other files as source of routing and usage metadata

---

## Maintenance Rules

When adding or changing a module:

1. update the markdown file first
2. update `modules.json`
3. update the relevant registry file for its layer
4. update compositions only if routing meaningfully changes

When removing or renaming a module:
- update all references immediately
- preserve consistency across registry files
- update examples and integration docs if necessary

---

## Validation Coverage

The registry is validated by the Forge CLI rather than JSON Schema alone:

- JSON syntax and schema validation for all registered registry documents
- registered-path containment and existence checks
- cross-reference and pack-reference checks
- deterministic semantic invariants across compositions, routing, template bindings, and contract registrations
- template output-schema binding validation
- explicitly declared API/event contract fixture compatibility checks

Run the complete local validation set from the Forge root:

```bash
python -m forge_cli --root . validate
```

Contract fixture validation is intentionally bounded: it proves only the registered JSON Schema fixtures in their declared directions, not runtime delivery or generalized consumer compatibility.

---

## Future Evolution

Likely future improvements include:

- automatic registry generation from module metadata
- broader semantic analysis beyond deterministic invariants
- generalized schema-diff compatibility inference
- additional runtime-state evolution tools

Keep additions disciplined.
Do not create many small registry files unless they clearly reduce ambiguity.

---

## Naming Note

Use stable ids such as:
- `behavior.review`
- `domain.spring`
- `template.review_report`
- `checklist.delivery`
- `report.incident`
- `engine.discover`
- `workflow.full_default`

Use ids consistently across registry files.

---

## Short Reminder

The registry is:
- an index
- a routing aid
- a machine-readable companion

It is not a replacement for the markdown architecture itself.
