---
title:              Session Tokens Audit Revalidation — cumulative counter vs context threshold
date:               2026-07-23
type:               investigation
status:             resolved
session_id:         3eae8036-e679-4a09-be65-144e738741e0
services:           [opencode, database, workflows, settings, groq]
tickets:            [MNT-145]
tags:               [session-history, compaction, tokens, opencode-export, audit, cost]
related:            [2026-07-16-session-history-tokens-null.md]
---

# Session History & Token Consumption Audit (Revalidated)

> This page merges the original audit (192-row DB analysis, 8 recommendations) with the
> revalidation that corrected two causal claims. The original analysis (now deleted)
> was at `2026-07-23-session-tokens-audit.md` (deleted).
>
> **Status update (2026-08-03, Consistency Agent):** the build plan referenced below has
> been executed. Verified on master: compaction is live (`demetra/workflows/build.py:79`)
> driven by the non-cumulative `context_tokens` metric (last assistant message input +
> cache read, `demetra/services/opencode.py:225`), the `context_tokens` and `model`
> columns exist (`demetra/library/tables.py:114-115`), and the Groq input is capped
> (`PLAN_OUTPUT_MAX_CHARS`, `demetra/services/groq.py:106`) — all landed in commit
> `47d428d`. Still open: recommendation 3 (the broad `except Exception` remains at
> `demetra/workflows/cleanup.py:76,103`) and recommendation 4 (no TTL cache on the
> export). The "dead code" / pending-recommendation framing below is kept as the
> historical record of the audit.

## TL;DR

Demetra records one row per workflow step (`plan`, `build`, `completed`, `failed`,
`awaiting_input`) into the `session_history` table by shelling out to
`opencode export <session_id>` and summing the token fields. A `CONTEXT_COMPACTION_THRESHOLD`
(default 100 k) is supposed to trigger `/compact` during the build loop via
`check_and_compact_context`. Querying the Odin DB (`192.168.1.100:5432`,
192 rows / 18 sessions) shows the median `build` row is **~15 M tokens** with a p99 of
**40 M** — three orders of magnitude over the threshold — and that **25% of rows are NULL**
(48 / 192). Revalidated every claim against the working tree, git history, and Odin DB:
all 192-row statistics reproduced exactly, but two causal claims were refuted: the
NULL-length rows were caused by the already-fixed pipe truncation (not cleanup ordering),
and "compaction never fires" is wrong — it was live for most of the sample and fired
constantly because `length` is a **cumulative** session counter compared against a
**context-size** threshold. The compaction feature cannot work as designed: its threshold
input can only grow, so it triggers on every build iteration after the first few messages.
The fix is a metric change (current context from the last assistant message of `opencode
export`), not re-enabling the existing code.

---

## Net effect

The compaction feature is dead code as-is, and even if re-enabled the threshold is far
below any realistic context size. The recorded `length` column is dominated by cache
reads (95.9% of all tokens in the sample), making it a poor cost signal. The recording
flow silently drops rows in two situations — making the dataset untrustworthy for
billing/observability work — and has no `model` dimension, so per-model cost analysis
is impossible. Two of the original audit's recommendations were dropped as refuted, one
as useless; the corrected audit and a hard-constraints build plan are in the repo root.

## How the current flow works

### Token extraction

**File:** `demetra/services/opencode.py:142` — `get_opencode_session_tokens` runs
`opencode export <session_id>` and reads `info.tokens.{input,output,reasoning}` plus
`info.tokens.cache.{read,write}`. The export is run through
`demetra/services/subprocess.py:47` (`run_command_to_file`) because the OS pipe buffer
truncates output around 64 KB. Each value passes through
`non_negative_int` (`demetra/services/utils.py:119`). If any of `input` / `output` /
`reasoning` is missing or negative, the function returns `None` and the row is recorded
with all token columns NULL.

### Length calculation

**File:** `demetra/library/models.py:52` — `TokenUsage.total` =
`input + output + reasoning + cache_read + cache_write`. This is what
`get_opencode_session_length` returns and what `length` stores.

### Storage

**File:** `demetra/services/database.py:942` — `record_session_step_history` writes
one `session_history` row per call. The schema is in
`demetra/library/tables.py:97`, the dataclass in `demetra/library/models.py:57`. Two
Alembic migrations created the table and added the token columns:
`migrations/versions/f1a2b3c4d5e6_add_session_history_table.py` and
`migrations/versions/a2b3c4d5e6f7_add_session_history_token_columns.py`.

### Recording call sites

| Step | File | Note |
|---|---|---|
| `plan` | `demetra/workflows/plan.py:82` | after the session is saved |
| `build` | `demetra/workflows/build.py:33` | inside `check_and_compact_context`; caller at `build.py:77` is **commented out** |
| `completed` | `demetra/workflows/cleanup.py:69` | swallowed in a broad `except Exception` at `cleanup.py:74` |
| `failed` | `demetra/workflows/cleanup.py:95` | same caveat as `completed` |

### Compaction

**File:** `demetra/workflows/build.py:19` — `check_and_compact_context` reads current
usage, records it, and shells out to `opencode_compact_session`
(`demetra/services/opencode.py:204`) when `length > CONTEXT_COMPACTION_THRESHOLD`
(`demetra/settings.py:40`, default 100 000). **Only caller:**
`demetra/workflows/build.py:79` — was commented out at audit time (MNT-145);
re-enabled in commit `47d428d` ("Optimize tokens consumption") after the audit.

## DB findings (Odin, 192.168.1.100:5432)

Re-ran the full query battery — every figure in the original audit reproduced exactly
(build avg is 16.8 M; the audit had rounded to 16.7 M):

```text
total_rows:        192     unique_sessions: 18     first: 2026-07-16  last: 2026-07-22
sum_length:        1,945,130,043
median_length:     10,253,566
mean_length:       13,507,848
sum_input:         71,627,362
sum_output:        6,018,679
sum_reasoning:     2,700,870
sum_cache_read:    1,864,783,132   (95.9% of all tokens)
sum_cache_write:   0
```

### Threshold breaches

| Length threshold | Rows over |
|---|---|
| > 100 k | 143 / 192 (74.5%) |
| > 1 M | 128 / 192 (66.7%) |
| > 10 M | 73 / 192 (38.0%) |
| > 40 M | 3 / 192 (1.6%) |

### Per-step distribution

| Step | n | avg | p50 | p90 | p95 | p99 | NULL length |
|---|---|---|---|---|---|---|---|
| build | 100 | 16.8 M | 14.9 M | 31.3 M | 37.3 M | 40.0 M | 31 |
| failed | 54 | 10.5 M | 6.9 M | 20.4 M | 25.3 M | 37.5 M | 10 |
| plan | 20 | 2.4 M | 0.7 M | 8.6 M | 11.9 M | 12.6 M | 5 |
| completed | 16 | 20.7 M | 22.2 M | 36.5 M | 38.5 M | 40.2 M | 2 |
| awaiting_input | 2 | 0.7 M | — | — | — | — | 0 |

### Sessions with no length data at all

```text
ses_093a105c8ffeAfoNF0eKjA9XXq   4 rows
ses_09416fcdeffeegOO9AxgsFoN0i   12 rows
ses_094e1f9ecffeNpkybkydRRlPYh   13 rows
ses_0937edfd8ffe9k1Y5s9ekQGSI2   9 rows
```

### Daily volume

| Date | Rows | Sum length |
|---|---|---|
| 2026-07-16 | 44 | 0 (all NULL) |
| 2026-07-17 | 12 | 54.9 M |
| 2026-07-20 | 96 | 1 206.6 M |
| 2026-07-21 | 32 | 578.0 M |
| 2026-07-22 | 8 | 105.6 M |

## `length` is cumulative — the audit's central blind spot

**File:** `demetra/library/models.py:53` — `TokenUsage.total` sums
`input + output + reasoning + cache_read + cache_write` from session-level
`info.tokens` of `opencode export`.

Build rows reach 40 M tokens — no model context is that large, so these are running
totals for the whole session (confirmed by the 8.2 M single-reading measured in
[[2026-07-16-session-history-tokens-null]]). Consequences:

- The "0 shrink events ⇒ compaction never ran" query is invalid — a cumulative counter
  cannot decrease even when `/compact` succeeds.
- Comparing it to `CONTEXT_COMPACTION_THRESHOLD` (100k, `demetra/settings.py:40`) means
  ~74% of rows are permanently "over threshold"; `/compact` fired on virtually every
  build iteration while enabled.
- Excluding cache reads doesn't help — `input + output + reasoning` is also monotonic.

## Compaction timeline (git history)

- `efbf4c7` (2026-07-06) — MNT-122 adds `check_and_compact_context`.
- `5f8e428` (2026-07-21 14:12 +03) — "MNT-145: Disable context compaction" comments out
  the only caller (**File:** `demetra/workflows/build.py:77`).

So compaction was *live* for most of the sampled period (07-16 → 07-21), contradicting
the audit's "never actually fires" claim. The constant firing is the likely motivation
for MNT-145.

## NULL rows: ordering claim refuted, truncation timeline confirmed

The audit claimed rows go NULL because recording runs after `git_cleanup` removed the
worktree. False in every committed version: the `failed` row is written at
`demetra/workflows/cleanup.py:95`, `git_cleanup` at `cleanup.py:103`; the `completed`
row is written in `commit_and_push` (`cleanup.py:69`), before `cleanup_workflow` runs.

The DB timeline instead matches the pipe-truncation fix from
[[2026-07-16-session-history-tokens-null]] exactly: all 48 NULL rows are timestamped
before `f96b07f` ("Fix session tokens countes", 2026-07-17 00:08 +03) — 44 on 07-16,
the last 4 at 00:01–00:02 on 07-17 — and there are **zero** NULLs in the 144 rows
since. Solved problem; no action needed.

## Smaller corrections

- `extract_plan` is at `demetra/services/groq.py:101`, not `:90` (`:90` is inside
  `process_text_with_groq`); the truncate-before-Groq recommendation itself stands.
- `record_session_step_history` is at `demetra/services/database.py:942` in the working
  tree (the audit's `:929` matched HEAD; an uncommitted `get_session_id_by_task_id` was
  added above it).
- `cache_write_tokens = 0` in all 192 rows **and** in the live payload measured on Odin
  on 07-16 — likely genuine opencode behaviour for these models, not a parser bug.
- The proposed 10 s TTL cache on the export has limited benefit (one export per build iteration,
  minutes apart, so a cache would rarely hit) and the `length = -1` sentinel for NULL sessions would skew aggregates
  that currently ignore NULLs correctly.

## Recommendations (ranked by impact, corrected)

1. **Re-enable context compaction with a non-cumulative metric** — re-enable `build.py:77`
   but change the threshold input from `TokenUsage.total` (cumulative session counter) to the
   last assistant message's token count from `opencode export`. The old threshold of 100 k
   compared against a cumulative counter meant compaction ran on every build iteration.

2. **Stop including cached reads in the compaction decision** — `TokenUsage.total`
   (sum of all five fields) is dominated by cache reads. Use
   `input + output + reasoning` for the threshold check, keep `length` for
   observability, and consider adding a separate `billable_tokens` column.

3. **Fix the silently-dropped rows** — `record_session_step_history` is called from
   `cleanup.py:69` / `:95` with a broad `except Exception` that hides `opencode export`
   failures. NULL rows are already fixed (pipe-truncation), but the broad catch still
   suppresses genuine failures for other reasons.

4. **Lower the recording frequency on the build loop** — once compaction is re-enabled,
   `check_and_compact_context` will run per build iteration and shell out to
   `opencode export` each time. Cache the export per `session_id` with a short TTL
   (e.g. 10 s) inside `get_opencode_session_tokens`. (Limited benefit — iterations are
   minutes apart — but cheap to add.)

5. **Add a `model` column to `session_history`** — there is no way today to attribute
   cost to a specific model. The current model is decided per step (plan / build /
   review) in `demetra/settings.py:111`. A new Alembic migration
   (`add_session_history_model_column`) and matching field on
   `demetra/library/models.py:57` plus `demetra/services/database.py:491` would unlock
   per-model cost dashboards.

6. **Investigate `cache_write_tokens = 0` everywhere** — the column exists in
   `demetra/library/tables.py:108` but no row in the sample has a non-zero value.
   Live payload inspection suggests this is genuine opencode behaviour, not a parser bug.

7. **Truncate long plan output before Groq summarisation** — `extract_plan` at
   `demetra/services/groq.py:105` ships the full plan output. Capping the input to the
   last ~8 k tokens before the LLM call would cap cost on long planning iterations.

## Open questions

- Does `opencode export` expose per-message token usage (needed for the current-context
  metric)? Blocking prerequisite — Step 1 of the build plan verifies the real schema.
- Is `cache.write` ever non-zero for the opencode-go models in use?
- Could not verify whether the four all-NULL sessions are recoverable: SSH to Odin was
  denied (publickey), and their worktrees are gone.

---

## Follow-ups

- ~~Execute `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md` (repo root): context metric from last
  assistant message, re-enable `build.py:77`, `model` + `context_tokens` columns,
  Groq input cap.~~ **Done** in `47d428d` — see the status note at the top of this page.
- Remaining from the recommendations: #3 (broad `except Exception` in
  `demetra/workflows/cleanup.py:76,103`) and #4 (short-TTL cache on `opencode export`).

## References

- Related: [[2026-07-16-session-history-tokens-null]]
- Root docs: `wiki/audits/2026-07-23-session-tokens/RESULT.md` (corrected audit), `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md` (implementation plan)
