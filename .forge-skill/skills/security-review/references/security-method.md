# Security Review Method

## Threat Surface

Review identity and session handling, object- and function-level authorization, tenant boundaries, input parsing and injection, output encoding, file/path handling, network egress, deserialization and execution, secrets, cryptography, logging, configuration, dependency trust, and failure behavior.

For each boundary identify attacker capability, controlled data, sensitive operation, existing controls, bypass conditions, and observable impact. Apply framework-specific knowledge only after confirming the actual runtime and version.

## Calibration

Critical findings require a credible path to severe compromise such as broad data exposure, remote execution, authentication collapse, or destructive cross-tenant action. High findings cause significant compromise under practical conditions. Medium findings need meaningful prerequisites or have narrower impact. Low findings are localized hardening gaps.

Confidence describes evidence quality, not severity. Lower confidence when routing, deployment controls, or caller behavior is missing.

## Remediation

Fix at the trust boundary: server-side authorization, parameterized queries, contextual output encoding, allowlisted parsing, managed secrets, proven cryptographic primitives, least privilege, and explicit secure defaults. Add a regression test that fails without the control and does not depend on a production exploit.
