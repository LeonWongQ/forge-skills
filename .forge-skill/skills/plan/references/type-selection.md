# Plan Type Selection Guide

## Decision Tree

```
User wants a plan
  ├─ Is the goal to build something NEW?
  │   ├─ New feature → implementation-plan.md
  │   ├─ New system/module → implementation-plan.md
  │   ├─ Migration/upgrade → implementation-plan.md
  │   └─ Rollout/deployment → implementation-plan.md
  │
  ├─ Is the goal to IMPROVE existing code structure?
  │   ├─ Reorganize classes/packages → refactor-plan.md
  │   ├─ Reduce duplication → refactor-plan.md
  │   ├─ Improve naming/clarity → refactor-plan.md
  │   ├─ Split large classes → refactor-plan.md
  │   ├─ Modernize patterns → refactor-plan.md
  │   └─ Reduce coupling → refactor-plan.md
  │
  └─ Is it UNCLEAR?
      └─ Ask: "Is this a new implementation or a refactoring of existing code?"
```

## Key Distinguishing Signals

| Signal | Implementation Plan | Refactor Plan |
|--------|-------------------|---------------|
| Primary verb | build, create, implement, add | refactor, restructure, clean up, reorganize, split, extract |
| Starting point | requirements, design, spec | existing code that works |
| Success criterion | new functionality works | same functionality, better structure |
| Risk profile | new bugs in new code | regressions in existing behavior |
| Template | `.forge-skill/forge/templates/implementation-plan.md` | `.forge-skill/forge/templates/refactor-plan.md` |
| Primary behavior | none (task-level) | `.forge-skill/forge/behaviors/refactor.md` |

## Edge Cases

- **Performance optimization**: if structural changes needed → refactor-plan; if config/algorithm only → lightweight implementation-plan
- **Bug fix + refactor**: separate into two plans. Fix first, refactor second. Never mix.
- **Design change**: if behavior changes → implementation-plan; if only structure changes → refactor-plan
