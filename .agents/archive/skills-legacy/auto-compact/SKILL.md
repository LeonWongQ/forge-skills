---
name: auto-compact
description: >-
  Proactive context management — monitors for context-pressure signals (system reminders,
  performance degradation, long conversations) and triggers compaction at optimal thresholds.
  Model-aware: 200K-standard models compact at ~160K tokens (80%), 1M-capable models
  compact at ~800K tokens (80%). ONLY activates for models in the supported list below;
  if the current model is not recognized, skip auto-compaction entirely.
  Triggers: 上下文要满了, compact, 压缩, context limit, token limit, summarize conversation.
allowed-tools: [Bash, Read, Glob, Grep]
context: inherit
---

# Auto-Compact — Proactive Context Management

## ⚠️ Hard Gate — Read First

**This skill ONLY applies to models listed in the table below.**

Before doing anything else, check which model you are running on:

1. **How to detect your model**: Look for model identity in your system prompt. In Codex, check for text like "You are powered by the model deepseek-v4-pro" or check the `<env>` block for `model` / `cliModel` fields. If running on a third-party platform (OpenRouter, DeepInfra, SiliconFlow, etc.), the model name is typically in the first system message.
2. If your model **matches** a row (case-insensitive partial match on the model column) → apply the corresponding threshold.
3. If your model **does NOT match** any row → **STOP. Do nothing.** This skill does not apply.
4. If you **cannot determine** your model at all → assume unsupported and skip.

Do not guess. Do not approximate. When in doubt, skip.

---

## Supported Models & Thresholds

### Anthropic

| Model | Context | 80% Threshold |
|-------|:------:|:------------:|
| Codex Haiku 4.x | 200K | ~160K |
| Codex Sonnet 4.x | 200K (1M beta) | ~160K |
| Codex Opus 4.x | 200K (1M beta) | ~160K |
| Codex 3.5 Sonnet / Haiku | 200K | ~160K |
| gpt-5.6-terra | 256K | ~205K |

### DeepSeek

| Model | Context | 80% Threshold | Notes |
|-------|:------:|:------------:|-------|
| deepseek-v4-pro | 1M | ~800K | 1.6T MoE, 49B active |
| deepseek-v4-flash | 1M | ~800K | 284B MoE, 13B active |
| DeepSeek V3.2 | 128K | ~102K | |

### Kimi（月之暗面 / Moonshot AI）

| Model | Context | 80% Threshold |
|-------|:------:|:------------:|
| kimi-k2.6 | 256K | ~205K |
| kimi-k2.5 | 256K | ~205K |

### GLM（智谱 / Z.ai）

| Model | Context | 80% Threshold | Notes |
|-------|:------:|:------------:|-------|
| glm-5.2 | 1M | ~800K | 128K max output |
| glm-5.1 | 200K | ~160K | |

### Qwen（阿里 / Alibaba）

| Model | Context | 80% Threshold |
|-------|:------:|:------------:|
| qwen3.7-max | 1M | ~800K |
| qwen3.7-plus | 1M | ~800K |
| qwen3.6-flash | 1M | ~800K |
| qwen3.5-plus | 1M | ~800K |
| qwen3.5-flash | 1M | ~800K |

### MiniMax

| Model | Context | 80% Threshold |
|-------|:------:|:------------:|
| MiniMax-M2.5 | 200K | ~160K |

> **Maintenance**: Last updated 2026-07. To add a model: confirm context window from vendor docs,
> compute 80% threshold, add a row. Threshold = floor(context_window × 0.8).

---

## Context-Pressure Signals

Watch for these signals in `<system-reminder>` blocks or your own awareness:

| Signal | Severity | Action |
|--------|:--------:|--------|
| "context usage" or "context length" mention | 🟡 | Note, compact after current task |
| "conversation has been summarized" | 🟠 | Compact before next task |
| "some context may be summarized" | 🟠 | Compact immediately |
| Response latency noticeably increased | 🟡 | Consider compacting |
| You can't recall early conversation details | 🟠 | Compact now |
| System reminder about token limits | 🔴 | Compact NOW |
| Forced truncation / cut-off | 🔴 | Already too late — compact immediately |

## Compaction Protocol

### When

1. **Proactive** (best): At the end of a completed task, before starting the next.
2. **Reactive**: On 🟠/🔴 signal, finish current thought in ≤2 sentences, then compact.
3. **Phase boundary**: Between forge workflow phases (Explore → Plan → Implement).

### How

```
/compact
```

### Before Compacting

- Save critical findings to `.Codex/memory/` or write to files
- Complete any in-progress tool calls
- Finish the current atomic task step

## Anti-Patterns

- ❌ Ignore system warnings — compact immediately, not "after this next thing"
- ❌ Compact mid-task or during tool execution
- ❌ Compact for unsupported models
- ❌ Compact every turn — target every ~20–30 turns or when signaled
