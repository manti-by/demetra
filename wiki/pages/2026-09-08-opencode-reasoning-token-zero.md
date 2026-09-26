---
title:              OpenCode Reasoning Token History Is Zero
date:               2026-09-08
type:               investigation
status:             resolved
session_id:         "-"
services:           [opencode, database, api]
branch:             "master"
tickets:            []
tags:               [opencode, session-history, reasoning-tokens]
related:
- 2026-07-23-session-tokens-audit-revalidation.md
---

# OpenCode Reasoning Token History Is Zero

## TL;DR

Demetra persists `reasoning` from `opencode export` unchanged — zeros originate in OpenCode, not in API/frontend/DB. Pre-AI-SDK-usage OpenCode read the obsolete `usage.reasoningTokens` field and exported zero even when the provider supplied a count; fix is updating OpenCode and verifying raw export for a reasoning model.

---

## Token flow

**File:** `demetra/services/agents/opencode.py:432` — `get_opencode_session_tokens` reads `info.tokens.reasoning` → `TokenUsage(reasoning=non_negative_int(tokens.get("reasoning")))`.

**File:** `demetra/services/persistence/database.py:2094` — `record_session_step_history` persists `usage.reasoning` to `session_history.reasoning_tokens`; API only serializes/sums stored column. No Demetra layer converts nonzero to zero.

## Root cause

OpenCode previously read `usage.reasoningTokens`; current code prefers `usage.outputTokenDetails?.reasoningTokens` (newer AI SDK location). Upstream: `anomalyco/opencode@a915fe7` (2026-04-13). Prior audit recorded 2,700,870 reasoning tokens from exports, confirming pipeline supports nonzero.

## Resolution

Upgrade OpenCode CLI to version containing the SDK update, then verify:

```sh
opencode export <session-id> | jq '.info.tokens'
```

If `.reasoning` is zero there, Demetra correctly stores zero. Existing history rows with zero cannot be corrected from aggregates.

---

## Follow-ups

- Confirm deployed OpenCode version and raw export from a new reasoning-capable session.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-23-session-tokens-audit-revalidation]]
- External: https://github.com/anomalyco/opencode/commit/a915fe74be24d4df9caf4c5b0e0f60133367b00d
