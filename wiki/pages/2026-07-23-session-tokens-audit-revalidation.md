---
title: Session History & Token Consumption Audit (Revalidated)
date: 2026-07-23
type: investigation
status: resolved
session_id: 3eae8036-e679-4a09-be65-144e738741e0
services: [opencode, database, workflows, settings, groq]
branch: "-"
tickets: [MNT-145]
tags: [session-history, compaction, tokens, opencode-export, audit, cost]
related: [2026-08-18-migrate-llm-groq-to-openrouter.md, 2026-07-16-session-history-tokens-null.md, 2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-opencode-v2-session-token-accounting.md]
---

# Session History & Token Consumption Audit (Revalidated)

> Merges original audit (192-row DB analysis, 8 recommendations) with revalidation that corrected two causal claims. Original at `2026-07-23-session-tokens-audit.md` (deleted).
>
> **Status (2026-08-03):** Compaction live (`workflows/build.py:79`) via non-cumulative `context_tokens` (`services/opencode.py:225`), `context_tokens`/`model` columns exist (`library/tables.py:114-115`), Groq input capped (`PLAN_OUTPUT_MAX_CHARS`, `services/groq.py:106`) — commit `47d428d`. Still open: rec 2 (cached reads in compaction), rec 3 (broad `except Exception` in `cleanup.py`), rec 4 (no TTL cache).
>
> **Correction (2026-10-16, see the 2026-10-16 note below):** "Compaction live" was never true — the compact command was passed as the *message positional*, so it cost a full-context turn without shrinking context. Fixed under MNT-251. Rec 3 is no longer a finding: the broad cleanup guard is the accepted, `# noqa: BLE001` workflow-cleanup pattern documented in `AGENTS.md`.

## TL;DR

One row per workflow step is recorded from `opencode export` token totals. Odin DB (192 rows / 18 sessions) shows median `build` row ~15 M tokens (p99 40 M) vs `CONTEXT_COMPACTION_THRESHOLD` 100 k, and 25% NULL rows — but two claims were refuted: NULLs were already-fixed pipe truncation (not cleanup ordering), and "compaction never fires" is wrong — it was live and firing constantly because `length` is cumulative compared against a context-size threshold. Fix is a non-cumulative metric from the last assistant message. **Superseded 2026-10-16:** the threshold was crossed and the call attempted, but no compaction ever happened (command passed as the message positional); see the 2026-10-16 note below.

## Net effect

Compaction was dead/broken as designed (cumulative counter vs context threshold → fires every iteration). `length` is 95.9% cache reads — poor cost signal. Two silent row-drop paths and no `model` dimension.

## How the flow works

- **Extraction** `services/opencode.py:142` `get_opencode_session_tokens` — `opencode export <session_id>` via `services/subprocess.py:47` `run_command_to_file` (avoids 64 KB pipe truncation), `non_negative_int` (`services/utils.py:119`).
- **Length** `library/models.py:52` `TokenUsage.total` = input+output+reasoning+cache_read+cache_write.
- **Storage** `services/database.py:942` `record_session_step_history`, schema `library/tables.py:97`, migrations `f1a2b3c4d5e6_add_session_history_table` / `a2b3c4d5e6f7_add_session_history_token_columns`.
- **Call sites:** `plan` `workflows/plan.py:82`, `build` `workflows/build.py:33` (caller `:77` commented out at audit time), `completed` `workflows/cleanup.py:69`, `failed` `:95` (both behind broad `except Exception`).
- **Compaction** `workflows/build.py:19` `check_and_compact_context` → `opencode_compact_session` (`services/opencode.py:204`) when `length > CONTEXT_COMPACTION_THRESHOLD` (`settings.py:40`, 100 k). Only caller `build.py:79`.

## DB findings (Odin 192.168.1.100, 192 rows)

```
total:192  sessions:18  sum_length:1,945,130,043  median:10,253,566  mean:13,507,848
sum_input:71M  sum_output:6M  sum_reasoning:2.7M  sum_cache_read:1,864M (95.9%)  sum_cache_write:0
>100k:143/192  >1M:128  >10M:73  >40M:3
```

| Step | n | avg | p50 | p90 | p99 | NULL |
|------|---|-----|-----|-----|-----|------|
| build | 100 | 16.8M | 14.9M | 31.3M | 40.0M | 31 |
| failed | 54 | 10.5M | 6.9M | 20.4M | 37.5M | 10 |
| plan | 20 | 2.4M | 0.7M | 12.6M | 12.6M | 5 |
| completed | 16 | 20.7M | 22.2M | 40.2M | 40.2M | 2 |

4 sessions have all-NULL history. Daily: `07-16` 44 rows all NULL, `07-17` 12 (54.9M), `07-20` 96 (1.2B), `07-21` 32 (578M).

## `length` is cumulative — central blind spot

`TokenUsage.total` sums session-level `info.tokens` — build rows at 40 M are running totals, not context size. So "0 shrink events ⇒ never ran" is invalid, and `>100k` (74%) means compaction fired every iteration while enabled.

## Compaction timeline

- `efbf4c7` (2026-07-06) MNT-122 adds `check_and_compact_context`.
- `5f8e428` (2026-07-21) MNT-145 comments out caller `build.py:77`. So live for most of sample (07-16→07-21) — constant firing likely motivated MNT-145.

## NULL rows: ordering claim refuted, truncation confirmed

Claim that recording after `git_cleanup` caused NULLs is false — `failed` at `cleanup.py:95` before `git_cleanup` `:103`, `completed` at `:69` before `cleanup_workflow`. Timeline matches pipe-truncation fix `f96b07f` (2026-07-17 00:08): all 48 NULLs before fix (44 on 07-16 + 4 at 00:01-02 on 07-17), zero NULLs in 144 rows since. Solved; no action.

## Smaller corrections

- `extract_plan` at `services/groq.py:101` not `:90`; `record_session_step_history` at `:942` (audit's `:929` matched older HEAD); `cache_write_tokens=0` in all rows and live payload — genuine opencode behavior; proposed 10s TTL cache has limited benefit (one export per build iteration, minutes apart).

## Recommendations (ranked, corrected)

1. **Re-enable compaction with non-cumulative metric** — last assistant message's tokens from `opencode export` (not `TokenUsage.total`).
2. **Exclude cache reads from compaction** — use input+output+reasoning for threshold; keep `length` for observability. *(Still open: `usage.context = msg_input + msg_cache_read` at `services/agents/opencode.py:524`.)*
3. **Fix silently-dropped rows** — broad `except Exception` in `cleanup.py` hides export failures. *(Still open, deliberate: `:134,179`.)*
4. **Lower recording frequency** — short TTL cache on export. *(Still open; limited benefit.)*
5. **Add `model` column** — attribution per model (`settings.py:111`). *(Done: `tables.py:162-163`.)*
6. **Investigate `cache_write_tokens=0`** — column `tables.py:108` always 0, genuine behavior.
7. **Truncate plan output before summarisation** — cap to ~8k tokens. *(Superseded MNT-168: now in `services/llm/openrouter.py`.)*

## Open questions

- Does `opencode export` expose per-message tokens (needed for current-context metric)?
- Is `cache.write` ever non-zero for these models?

## Update — 2026-10-16 15:08

The delta model recommended here shipped in [[2026-10-16-mnt-251-session-attribution-accounting]] (MNT-251 Phase 2). The cumulative-counter blind spot this page identified is fixed by storing exact per-invocation deltas rather than re-inserting the running total:

- `agent_sessions` holds one row per `(task_id, session_id)` with the cumulative cursor; `session_history` `kind='invocation'` rows store `delta = max(0, info.tokens - cursor)`.
- `_compute_total_tokens` sums only `kind='invocation'` rows and drops the legacy `row.length` fallback, so a resumed session no longer counts the same tokens many times.
- `context_tokens` stays a per-step snapshot (`input + cache.read`), excluded from the total — rec #2 here remains the deliberate design.
- `info.tokens` was measured **monotonic across a `/compact`**, so no cursor reset or compaction special-casing is needed.

Recommendation status: **#1 done** (non-cumulative metric + delta model); **#2 open/deliberate** (`usage.context = input + cache.read`); **#3 deliberate** (best-effort cleanup guards); **#4 open** (TTL cache, limited benefit — one file-backed export per invocation by design).

---

## Follow-ups

- ~~Execute `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md`~~ **Done** `47d428d`.
- Remaining: #2 cache reads in decision, #3 broad except, #4 TTL cache.

## Consistency notes

- **2026-08-19:** Plan extraction moved Groq → OpenRouter (`services/llm/openrouter.py`), legacy `groq.py` retained. See [[2026-08-18-migrate-llm-groq-to-openrouter]].
- **2026-08-23/27 / 2026-09-03:** Module moves — `services/opencode.py` → `services/agents/opencode.py`, compaction caller `workflows/build.py:100`→`:102`, `usage.context` at `:428`→`:524`, `context_tokens`/`model` at `tables.py:142`→`:162-163`, `cleanup.py` catches `:110,149`→`:134,179`.
- **2026-08-28:** Added `branch: "-"` frontmatter.
- **2026-10-16:** Compaction was never functional — `opencode_compact_session` passed `/compact` as the *message positional*, so opencode ran a normal full-context turn instead of compacting. The "firing constantly" reading above is the cost symptom of that no-op, not a working compact; `47d428d` made the counter non-cumulative but did not make compaction work. Fixed under MNT-251 ([[2026-10-16-mnt-251-session-attribution-accounting]]): `run --session <id> --command compact` on opencode 1.x, deliberately unsupported on v2, with a test that asserts the context actually shrank. See [[2026-10-16-opencode-v2-session-token-accounting]].

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-16-session-history-tokens-null]], [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-10-16-opencode-v2-session-token-accounting]]
- `wiki/audits/2026-07-23-session-tokens/RESULT.md`, `BUILD_PLAN.md`
