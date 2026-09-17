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

## Summary Quality Gates

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
