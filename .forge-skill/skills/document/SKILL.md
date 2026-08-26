---
name: document
description: >-
  Create, improve, or restructure documentation including API docs, architecture
  docs, READMEs, code comments, runbooks, migration guides, and release notes
  with accuracy, clarity, and audience-fit discipline.
  Use when the user says: document this, write documentation, create docs,
  generate javadoc, write README, document this API, create runbook,
  write architecture doc, add comments, improve documentation,
  写文档, 生成文档, 加注释, 写说明, 文档化, API文档.
  For any documentation authoring or improvement request.
allowed-tools: [Read, Glob, Grep, Bash(git diff, git log, git show, git status, git ls), Write]
---

# Document

## 1. Activation Sequence

1. Load forge kernel: `.forge-skill/forge/CLAUDE.md`, `.forge-skill/forge/AUTOLOAD.md`
2. Identify the documentation type from user intent:
   - API documentation (Javadoc, OpenAPI)
   - Architecture documentation (ADR, design doc, system overview)
   - README / getting-started
   - Code comments and inline documentation
   - Migration / changelog / release notes
   - Runbook / operational documentation
3. Detect technical domains from the subject:
   - Java code/docs → `.forge-skill/forge/domains/java.md`
   - Spring code/docs → `.forge-skill/forge/domains/spring.md`
   - Database docs → `.forge-skill/forge/domains/mysql.md`
   - Cache/Redis docs → `.forge-skill/forge/domains/redis.md`
   - Test docs → `.forge-skill/forge/domains/testing.md`
   - If no domain matches the subject, skip domain loading. Proceed with behavior + template + checklists only.
4. Compose forge modules per section 2
5. Execute: discover audience → gather context → draft → review → deliver
6. Deliver structured documentation

## 2. Forge Module Composition

| Module | Path | Role |
|--------|------|------|
| Behavior | `.forge-skill/forge/behaviors/document.md` | Primary: accuracy, clarity, audience fit |
| Domains | Detected from subject | Domain-specific terminology, conventions, context |
| Template | `.forge-skill/forge/templates/default.md` | Flexible output shape (documentation is format-diverse) |
| Checklists | `.forge-skill/forge/checklists/general-quality.md` | Baseline quality |
| | `.forge-skill/forge/checklists/delivery-checklist.md` | Usable output |
| Workflow | `workflow.full_default` | Full for non-trivial docs; light for small docs |

## 3. Core Discipline (from document.md)

### Documentation Priorities
1. **Accuracy**: the documentation must be correct. Wrong docs are worse than no docs.
2. **Clarity**: the intended reader must understand without external help.
3. **Audience fit**: write for the actual reader (new developer, experienced maintainer, ops engineer, end user).
4. **Maintainability**: documentation that rots quickly creates a false sense of security.

### Documentation Types and Focus

**API Documentation**
- Every public method: what it does, parameters, return value, exceptions, side effects
- Prefer behavior description over implementation description
- Include usage examples for non-obvious APIs

**Architecture Documentation**
- System boundaries, component responsibilities, data flow
- Key design decisions and their rationale (why, not just what)
- Constraints and assumptions

**README / Getting Started**
- What is this? (one sentence)
- Quick start (minimal steps to get running)
- Key concepts (if needed)
- Links to deeper docs (not everything goes in README)

**Code Comments**
- Explain WHY, not WHAT (the code says what)
- Document assumptions, edge cases, non-obvious behavior
- Keep comments close to the code they describe

**Runbook / Operational Docs**
- Common procedures (step-by-step)
- Troubleshooting guide (symptom → diagnosis → fix)
- Configuration reference
- Contact / escalation paths

### Quality Standards
- Use consistent terminology throughout
- Prefer active voice and direct language
- Break long sections with headings
- Include examples for abstract concepts
- Mark version-specific or environment-specific information

### Anti-Patterns
- Restating code without adding insight
- Documentation that contradicts the code
- Outdated information without a "last updated" marker
- Copy-pasting without adapting to audience
- Writing for yourself instead of the reader

## 4. Output Structure

```
## Document Type
<API doc / architecture / README / runbook / ...>

## Audience
<who will read this, what they need>

## Content
<the documentation, structured appropriately for the type>

## Maintenance Notes
<when this doc should be reviewed/updated, what triggers changes>
```

## 5. Guard

Before delivering:
- [ ] Document type and audience identified
- [ ] Content is accurate (verified against code/runtime if applicable)
- [ ] Language is clear and direct
- [ ] Examples included for non-obvious concepts
- [ ] Terminology is consistent
- [ ] Document is scannable (headings, lists, not walls of text)
- [ ] Not restating code without adding insight
- [ ] **Output**: Ask user for target path before writing. Do not overwrite existing files without confirmation. Default to inline display.
