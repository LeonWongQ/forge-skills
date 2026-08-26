---
name: bailian-api
description: Design, implement, debug, and review Alibaba Bailian and DashScope API integrations. Use for SDK setup, model invocation, streaming, structured output, tool calling, authentication, API errors, and production reliability. Do not use for encrypted Bailian workflow import artifacts; use bailian-workflow instead.
---

# Bailian API

Use the existing project SDK, endpoint conventions, and model configuration before adding new integration code. Preserve the current request and response contract unless the user explicitly requests a behavior change.

## Credential Boundary

- Before any command or code path that requires a DashScope or Bailian API credential, ask the user to confirm an available local credential source.
- Ask for an environment-variable name, protected local credential-file path, or approval to use a local masked prompt. Never ask for, print, or embed an API key in chat, command arguments, logs, source code, fixtures, or committed configuration.
- Keep API credentials separate from the Bailian workflow import key. An encrypted workflow artifact belongs to `bailian-workflow`.

## Workflow

1. Identify the target model, SDK or HTTP client, endpoint, intended capability, and current production contract.
2. Inspect existing client setup, retries, timeouts, request serialization, response parsing, and observability before changing code.
3. Confirm the local credential source before any authenticated operation.
4. Implement or review the narrowest change. Validate streaming lifecycle, structured-output schema handling, tool arguments, cancellation, retryability, and error classification as applicable.
5. Add focused tests with redacted fixtures. Record model, region or endpoint, SDK version, timeout, retry policy, and credential-source type without exposing secrets.

## Delivery

- Report the selected integration surface, contract preserved or changed, credential-source type, validation evidence, and operational limits such as timeout, retry, rate-limit, and rollback behavior.
- Do not report credentials, full authorization headers, or sensitive raw prompts and responses.
