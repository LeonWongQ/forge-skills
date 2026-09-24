# Skill Training Lifecycle

This reference is authoritative for lifecycle state, transition gates, and
release evidence. Phase numbers describe delivery order, not automatic
execution. Every mutating transition remains operator-controlled unless an
explicit feedback threshold below says otherwise.

## Implemented Phases

1. **Responsibility and lifecycle contract (`COMPLETE`)** separates evidence
   records, reviewed Summary knowledge, and executable project Overlays. A
   Summary cannot be activated directly, and an Overlay never edits the global
   Skill.
2. **Persistence and traceability (`COMPLETE`)** provides versioned Overlay
   storage, source-Summary links and digests, one ACTIVE Overlay per project and
   Skill, and project-copy isolation.
3. **Overlay generation (`COMPLETE`)** builds a DRAFT from one or more reviewed
   Summary versions using confirmed rules, normalized deduplication, source
   traceability, and size limits.
4. **Human review and version management (`COMPLETE`)** supports editing,
   review, physical deletion of non-active versions, explicit activation, and
   disabling. Creation and review never activate an Overlay.
5. **Runtime intervention (`COMPLETE`)** loads the ACTIVE project Overlay with
   the global Skill as supplemental pre-check and final-validation guidance.
   Invalid or unavailable Overlay data fails open to the unchanged global Skill.
6. **Runtime provenance (`COMPLETE`)** records applied Overlay identity,
   project, Skill, version, and content digest without duplicating its body in
   each evidence record.
7. **Evaluation and publication (`COMPLETE, PROVISIONAL EVIDENCE`)** runs
   deterministic structural checks followed by fixed-case Baseline-versus-
   Candidate LLM evaluation. Passing results are published but never activated.
   Activation revalidates the Baseline, global Skill, corpus, Candidate digest,
   and Summary sources. Full responses and reported usage remain in the project
   Skill evaluation directory. Baseline responses are cached by Skill, corpus,
   active Overlay, model, wire API, and endpoint digests; Candidate generation
   and blind judging always run fresh. Explicit retry refreshes the Baseline.
   Responses API refinement and evaluation use the same relay-compatible
   non-stream-requesting payload. If a relay returns server-sent events anyway,
   output is accepted only after `response.completed`; interrupted, failed,
   incomplete, malformed, or oversized streams fail closed without persisting
   partial model output.
   LLM configuration stores an API base URL and derives `/responses` or
   `/chat/completions` from the selected wire API. Legacy full endpoint values
   are normalized before use to prevent duplicate operation paths.
8. **Production feedback and automatic disabling (`COMPLETE`)** uses human-
   reviewed, Overlay-tagged records. When one exact ACTIVE Overlay has more than
   10 reviewed records and over 30 percent are EXCLUDED, it is disabled without
   activating an older version.

## Direct Host Capture

An enabled Skill's direct-host lifecycle starts with one call to
`scripts/begin_direct_invocation.py` with `--host <current-host>`, makes one
pre-execution Overlay lookup through `scripts/resolve_direct_overlay.py`, and
finishes with one post-result fallback attempt through
`scripts/record_direct_result.py`. A successful begin receipt supplies the
invocation ID and current Hook host to the fallback. The native Hook uses the
same ID and enriches the same unreviewed record instead of creating a duplicate.
If the current host's Hook is not configured, begin returns
`hookExpected=false` without creating a marker; the fallback remains valid and
must not be attributed to another configured host.

The resolver is read-only. The collector checks the same project allowlist and
writes to the project Skill database, so disabling a Skill stops both collection
and Overlay application. Retain applied Overlay identity in metadata without its
content. Collect only user-visible result evidence, never hidden reasoning.

The direct-host transport is strict and best-effort:

- Read `pythonExecutable` and `directCollectionTimeoutSeconds` from
  `forge-data/runtime.json`. Do not use the Windows `py` launcher, discover a
  replacement runtime, or switch interpreters after failure.
- Write UTF-8 JSON bytes directly to stdin; a PowerShell native text pipeline is
  not supported. Reject invalid UTF-8 and lone Unicode surrogates while preserving
  valid Chinese, emoji, and supplementary-plane characters.
- Attempt begin, lookup, and fallback at most once each with the configured
  timeout. Failure diagnostics may retain only the error type, interpreter path,
  and exit code, and must not delay delivery or trigger conversion or retry.

The database keeps one `(projectId, skill, invocationId)` record. The
Skill-contract result is canonical structured training input; the host-rendered
response is separate supporting evidence. An empty Hook result or a late Hook
after human review cannot alter the record. Hook-only evidence may be inspected
and reviewed but cannot source a Summary. A later unreviewed fallback may merge
into the invocation and become canonical.

Hook capture is Skill-agnostic. Normalize native output only for transport line
endings and never force it into a `code-review` schema. Store a content-free
quality profile in `metadata.hookCapture`, including Skill, host, response source,
attribution strength, matched Skills, format, and size. Preserve this metadata
regardless of whether Hook or fallback arrives first.

When a host provides stable turn identity for several Skills, assign one
`sharedCaptureId` and mark the records `SHARED_HOST_TURN`. Cursor generation
identity supports this grouping. Codex and Claude Code session-only events remain
ambiguous with multiple pending markers and use Skill-contract fallback. Present
Hook-only shared records once and apply one review action atomically to every
member. Members are non-reviewable until all writes publish as complete. Limit a
shared turn to 11 Skill databases, matching SQLite's atomic attached-database
limit; larger groups skip Hook capture and retain fallback collection. After a
Skill-contract result becomes canonical, its Skill-specific structured output is
reviewed independently.

Native Hook configurations are independent local-user settings for Codex,
Claude Code, and local Cursor. They may coexist, and configuring one does not
remove another. They do not cover cloud, remote, or container hosts unless the
same installation exists there. Managed registrations live in
`forge-data/learning-hooks.json`; a host is removed only by an explicit removal
action, while unrelated Hooks are always preserved. Configuration does not prove
invocation. The dashboard reads bounded, content-free outcomes from
`forge-data/hook-status/<host>.json`. Ambiguous events retain every marker and use
fallback rather than guessing or marking unrelated captures as missed. Never add
an unkeyed capture path.

## Summary Quality Gates

- Hook-only records are retained as supporting evidence and may be reviewed for
  audit purposes, but never enter deterministic or LLM-refined Summaries until a
  Skill-contract fallback becomes their canonical structured input.
- A `SHARED_HOST_TURN` uses one shared capture identity when the host supplies a
  stable turn-level identity. Cursor generation identity currently supports this;
  multiple Codex or Claude Code markers with only session identity stay ambiguous
  and use Skill-contract fallback. Hook-only members are shown and reviewed once
  across their linked Skills; Skill-contract results stay independently reviewable
  because their structured outputs may differ. Review is blocked until all Hook-only
  members publish completion. A shared turn is limited to 11 distinct Skill databases
  so the review remains one atomic SQLite transaction; larger turns use Skill-contract
  fallback instead of partial Hook capture.
- In a specialized deterministic extractor, ordinary Skill output becomes a
  candidate only when the same adjustment is supported by at least two
  independent records. An explicit `learningSignal` or a non-empty human review
  note may admit a single-record candidate. The generic fallback remains a
  review queue because it cannot infer semantic agreement safely.
- LLM refinement removes task-specific facts, current project or UI state, and
  subject-matter answers. Returning zero rules is valid when no reusable Skill
  adjustment remains.
- Refinement rejects replacement characters and isolated Unicode surrogates so
  damaged source text cannot become a new Summary version.
- Explicit refinement sends a bounded packet of reviewed effective content,
  review notes, candidate IDs and evidence to the configured model. All
  candidates receive a KEEP/DISCARD/CONFLICT decision before a second call
  synthesizes only KEEP candidates into at most six rules. Unknown citations,
  duplicate instructions, missing triggers and verification, oversized input,
  changed evidence, and malformed output fail without creating a version.
- The Summary review page displays classification reasons and linked source
  evidence. The labeled cases in `forge/evals/summary-refinement-cases.json`
  are an advisory starting set, not an approved judge calibration or evidence
  that the target precision and acceptance thresholds have been reached.

## Phase 9: Evaluation Qualification

Phase 9 is in progress and is required before treating Phase 7 evidence as a
production release signal. The initial case-coverage milestone is complete:
the current project's enabled `code-review`, `debug`, `plan`, `explain`, and
`explore` Skills each have at least three compatible read-only automated cases
covering representative, boundary, and adversarial behavior. This milestone
does not qualify an LLM judge or authorize automatic publication.

The remaining qualification work is:

- provide at least three independent HTTP-compatible, read-only cases for every
  Skill allowed to use automatic publication;
- cover representative, boundary, and known-failure behavior without using
  training-source records as the evaluation set;
- compare judge decisions with a human-labeled calibration set and require an
  operator-approved agreement threshold;
- run an explicit end-to-end evaluation against the configured real endpoint,
  verifying parsing, reported token usage, timeout behavior, artifact
  persistence, publication, and separate manual activation;
- expose sufficient per-case evidence in the dashboard for human inspection of
  failed or low-confidence decisions without direct SQLite access.

Until Phase 9 is accepted, reports must retain
`judgeCalibration=uncalibrated_user_approved_gate`; fewer than three compatible
cases remain LOW confidence and cannot publish automatically.

## Transition Invariants

- Summary generation, Summary review, Overlay generation, Overlay review,
  evaluation/publication, and activation are separate transitions.
- Model execution occurs only after an explicit operator action.
- Evaluation fails closed for missing compatible cases, fewer than three cases,
  failed structural checks, concurrent Overlay changes, changed Summary
  sources, or a changed active Baseline.
- Publication never implies activation.
- Automatic feedback control may disable the exact active Overlay only; it does
  not select or activate a replacement.
