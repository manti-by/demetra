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
related: [2026-07-23-session-tokens-audit-revalidation]
---

# OpenCode Reasoning Token History Is Zero

## TL;DR

Demetra persists the `reasoning` value returned by `opencode export` unchanged. The zero values are therefore not introduced by the session-history API, frontend, or database. OpenCode versions before its AI SDK usage update can read reasoning from the obsolete field and export zero even when the provider supplied a reasoning count; update OpenCode, then verify its raw export for a reasoning-capable model.

---

## Token flow

**File:** `demetra/services/agents/opencode.py:432`

`get_opencode_session_tokens` reads `info.tokens.reasoning` from `opencode export <session_id>` and passes it directly into `TokenUsage`.

```python
reasoning_tokens = non_negative_int(tokens.get("reasoning"))
usage = TokenUsage(
    input=input_tokens,
    output=output_tokens,
    reasoning=reasoning_tokens,
)
```

**File:** `demetra/services/persistence/database.py:2094`

`record_session_step_history` persists `usage.reasoning` directly to `session_history.reasoning_tokens`. The API only serializes and sums that stored column. No Demetra layer changes a nonzero reasoning count to zero.

## Root cause

OpenCode's session usage calculation previously read `usage.reasoningTokens`. Its current implementation uses `usage.outputTokenDetails?.reasoningTokens` first, because newer AI SDK responses put the count there. The upstream change is `anomalyco/opencode@a915fe7` (2026-04-13).

The prior session-token audit also recorded 2,700,870 reasoning tokens from OpenCode exports, confirming that Demetra's extraction and persistence path supports nonzero values.

## Resolution / verification

Upgrade the deployed OpenCode CLI to a version containing the upstream usage update. For a new session run with a reasoning-capable model, verify the source value before inspecting Demetra:

```sh
opencode export <session-id> | jq '.info.tokens'
```

If `.reasoning` is zero there, Demetra will correctly store zero. Existing history rows cannot be corrected from the aggregate exports once OpenCode has returned zero.

---

## Follow-ups

- Confirm the deployed OpenCode version and the raw export from a new reasoning-capable session.

## References

- Related: [[2026-07-23-session-tokens-audit-revalidation]]
- External: https://github.com/anomalyco/opencode/commit/a915fe74be24d4df9caf4c5b0e0f60133367b00d
