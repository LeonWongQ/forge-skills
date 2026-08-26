# Domain: Spring AI

## 1. Activation

Load this domain when the task involves Spring AI, LLM integration, prompt construction, tool calling, model invocation, retrieval/augmentation patterns, AI workflow orchestration, or output parsing from AI models.

**Auto-detect signals**: Spring AI imports (`org.springframework.ai.`), `ChatClient`, `ChatModel`, `ToolCallback`, `@Tool` annotation, prompt templates, `Document`/`DocumentReader`, `VectorStore`, `Advisor`, structured output converters.

---

## 2. Review Checklist

When reviewing Spring AI code, verify each item.

### 2.1 Prompt Construction
- [ ] Prompt assembly is centralized and reviewable — not spread across multiple layers
- [ ] System vs user vs tool instruction roles are clearly separated
- [ ] Dynamic content in prompts is validated and sanitized before injection
- [ ] Untrusted user input is constrained (character limit, format validation) before inclusion
- [ ] Prompt templates are version-controlled (not hardcoded strings scattered in code)
- [ ] A maintainer can see exactly what the model receives without tracing through 5 classes

### 2.2 Output Handling
- [ ] Structured output is enforced (`@StructuredOutput`, schema-guided response) — not free-form text parsing
- [ ] Output parsing has explicit failure handling: what happens when the model returns malformed JSON?
- [ ] No reliance on regex extraction of model output for business-critical values
- [ ] Response validation happens AFTER parsing, not before
- [ ] Default values or fallback behavior exist for every parsed field

### 2.3 Tool Calling Safety
- [ ] Every `@Tool` method validates its inputs independently (don't trust model-provided arguments)
- [ ] Tool side effects are bounded: what's the worst that could happen if called with wrong args?
- [ ] Tool authorization is enforced at the application layer, not relying on the model to "decide"
- [ ] Tool execution is auditable: logged with inputs, outputs, and caller context
- [ ] No tool can trigger irrecoverable actions (delete, send, publish) without confirmation or circuit breaker

### 2.4 Context and Memory
- [ ] Context window is bounded: conversation history has a max size limit
- [ ] Retrieval results are filtered for relevance before injection (not "top K whatever")
- [ ] Stale documents have TTL or version checks
- [ ] Memory/advisory chain is inspectable for debugging
- [ ] Token usage is monitored and alertable (cost + performance)

### 2.5 Error Handling and Reliability
- [ ] Provider failure is handled explicitly: timeout, retry, fallback
- [ ] Retry with backoff (not immediate retry loop)
- [ ] Graceful degradation: what does the user see when the model is unavailable?
- [ ] No hardcoded provider assumptions (model name, endpoint) — use configuration
- [ ] Circuit breaker or rate limiter on model calls
- [ ] User-facing failure mode is designed (not a raw stack trace)

### 2.6 Observability
- [ ] Prompt/response pairs are logged (with sensitive data masked)
- [ ] Token count and model latency are captured per request
- [ ] Tool calls are traced with inputs, outputs, and timing
- [ ] Correlation ID links model request to downstream actions
- [ ] Prompt changes can be compared between versions (prompt versioning)

### 2.7 Security and Privacy
- [ ] No secrets, PII, or credentials sent to the model unintentionally
- [ ] Sensitive data is masked before logging prompts/responses
- [ ] Retrieval corpus is access-controlled (not all documents visible to all users)
- [ ] Prompt injection through external content is mitigated (clear instruction/content separation)
- [ ] Model output displayed to users is sanitized (no raw tool outputs, no system instructions leaked)

---

## 3. Debug Heuristics

### Pattern: Model Returns Unexpected Output
- **Symptom**: Parsing fails, business logic breaks on model response, or response is off-topic
- **Common causes**: Prompt ambiguity, insufficient constraints, temperature too high, context window overflow pushing out instructions, retrieval noise confusing the model
- **Diagnose**: Log the exact prompt and response. Check if instructions are still in the prompt (or pushed out by context). Check retrieval relevance. Check token count.
- **Fix**: Add structured output; constrain with schema; reduce temperature; limit context injection; add output validation layer

### Pattern: Tool Called With Wrong Arguments
- **Symptom**: Tool execution fails with invalid input, or tool performs wrong action
- **Common causes**: Model hallucinating argument values, prompt not describing tool contract clearly, ambiguous parameter descriptions, multiple tools with similar names
- **Diagnose**: Log the exact tool call arguments. Check the tool description in the prompt — is it clear? Are there similar tools confusing the model?
- **Fix**: Validate all tool inputs at application layer; make tool descriptions more precise; add parameter constraints in tool definition

### Pattern: High Token Usage / Cost
- **Symptom**: Model calls consuming more tokens than expected, cost overrun
- **Common causes**: Unbounded conversation history, excessive retrieval results, large system prompt, repeated context in every request
- **Diagnose**: Check per-request token count. What's in the context window? Is history growing without bound? Are retrieval results too large?
- **Fix**: Cap history; trim or summarize old messages; filter retrieval to top 3-5 most relevant; cache common system prompts

### Pattern: Slow Model Response
- **Symptom**: User-facing latency spike on AI features
- **Common causes**: Large context window, streaming not enabled, provider throttling, long tool execution chain
- **Diagnose**: Check model latency metrics. Is context too large? Is streaming enabled? Are tools taking long?
- **Fix**: Stream responses; reduce context size; async tool execution where possible; add timeout with fallback

---

## 4. Error Patterns

| Error | Meaning | Common Causes | Fix Direction |
|-------|---------|---------------|---------------|
| `AiClientException` / `AiServiceException` | Provider call failed | Network, auth, rate limit, provider outage | Retry with backoff; check API key; check rate limits |
| `ParseException` on model output | Output not in expected format | Model returned free-form text, JSON malformed | Use structured output; add parsing fallback; validate before parse |
| `ToolExecutionException` | Tool call failed | Invalid arguments, tool unavailable, tool threw exception | Validate tool inputs; add tool error handling; check tool availability |
| Empty / null response | Model returned nothing | Prompt too restrictive, safety filter triggered, context overflow | Check safety filters; check prompt constraints; add null guard |
| `TokenLimitExceededException` | Context window exceeded | Unbounded history, large retrieval, large system prompt | Cap context; trim history; limit retrieval results |
| `RateLimitExceededException` | Provider rate limit hit | Too many concurrent requests, no rate limiting | Add rate limiter; batch requests; cache frequent calls |

---

## 5. Refactor Guidelines

When refactoring Spring AI code, verify:
- [ ] Prompt composition unchanged or improved: same instructions reach the model
- [ ] Tool definitions preserved: same tool names, descriptions, and parameter schemas
- [ ] Output parsing preserved: same response structure expected
- [ ] Error handling preserved: same fallback behavior on model failure
- [ ] Observability preserved: logging, tracing, metrics still captured
- [ ] Provider configuration unchanged: same model, endpoint, timeout

---

## 6. Verification Rules

- [ ] Prompt/response trace: log at least one full interaction to verify prompt assembly
- [ ] Malformed output test: simulate model returning bad JSON — does parsing fail gracefully?
- [ ] Tool input validation test: call tool with edge-case arguments — are they rejected properly?
- [ ] Provider failure test: simulate timeout or error — does the system degrade gracefully?
- [ ] Token usage check: verify context size is bounded under worst-case scenario
- [ ] Security review: verify no PII in logged prompts; verify tool authorization
