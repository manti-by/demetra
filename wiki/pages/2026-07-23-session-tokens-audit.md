---
title:              Session History & Token Consumption Audit
date:               2026-07-23
type:               investigation
status:             open
session_id:         -
services:           [opencode, database, workflows, settings]
branch:             -
tickets:            [MNT-145]
tags:               [session-history, compaction, tokens, opencode-export, audit, cost]
related:            [2026-07-16-session-history-tokens-null.md, 2026-07-23-session-tokens-audit-revalidation.md]
---

# Session History & Token Consumption Audit

> **Heads-up:** this page documents the **original** audit session. Two of its causal
> claims were later **refuted** by the revalidation in
> [[2026-07-23-session-tokens-audit-revalidation]] — see *Open questions* below for the
> corrections. Root doc: `wiki/audits/2026-07-23-session-tokens/RESULT.md` (corrected in place).

## TL;DR

Demetra records one row per workflow step (`plan`, `build`, `completed`, `failed`,
`awaiting_input`) into the `session_history` table by shelling out to
`opencode export <session_id>` and summing the token fields. A `CONTEXT_COMPACTION_THRESHOLD`
(default 100 k) is supposed to trigger `/compact` during the build loop via
`check_and_compact_context`. Querying the Odin DB (`192.168.1.100:5432`,
192 rows / 18 sessions) shows the median `build` row is **~15 M tokens** with a p99 of
**40 M** — three orders of magnitude over the threshold — and that **25% of rows are NULL**
(48 / 192). The compaction call site in the build loop is commented out, and 4 sessions
are entirely NULL. Recommendations: re-enable the call, drop cache reads from the cost
metric, fix the silently-dropped rows, cache the export, and add a `model` column.

---

## Net effect

The compaction feature is dead code as-is, and even if re-enabled the threshold is far
below any realistic context size. The recorded `length` column is dominated by cache
reads (95.9% of all tokens in the sample), making it a poor cost signal. The recording
flow silently drops rows in two situations — making the dataset untrustworthy for
billing/observability work — and has no `model` dimension, so per-model cost analysis
is impossible.

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

**File:** `demetra/services/database.py:929` — `record_session_step_history` writes
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
| build | 100 | 16.7 M | 14.9 M | 31.3 M | 37.3 M | 40.0 M | 31 |
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

### Compaction evidence

Querying for sessions where a later row's `length` is smaller than an earlier row's —
the only signal that `/compact` actually ran — returns **0 rows**.

### Daily volume

| Date | Rows | Sum length |
|---|---|---|
| 2026-07-16 | 44 | 0 (all NULL) |
| 2026-07-17 | 12 | 54.9 M |
| 2026-07-20 | 96 | 1 206.6 M |
| 2026-07-21 | 32 | 578.0 M |
| 2026-07-22 | 8 | 105.6 M |

## Recommendations (ranked by impact)

1. **Re-enable context compaction** — uncomment `demetra/workflows/build.py:77` so
   `check_and_compact_context` runs after each build iteration. With the current
   threshold and a p99 build length of 40 M, ~74% of rows are over the threshold — the
   dead code path is the primary driver of token blow-up.

2. **Stop including cached reads in the compaction decision** — `TokenUsage.total`
   (sum of all five fields) is dominated by cache reads. Use
   `input + output + reasoning` for the threshold check, keep `length` for
   observability, and consider adding a separate `billable_tokens` column.

3. **Fix the silently-dropped rows** — `record_session_step_history` is called from
   `cleanup.py:69` / `:95` with a broad `except Exception` that hides `opencode export`
   failures. Currently 48 / 192 rows (25%) are NULL — four whole sessions.

4. **Lower the recording frequency on the build loop** — once compaction is re-enabled,
   `check_and_compact_context` will run per build iteration and shell out to
   `opencode export` each time. Cache the export per `session_id` with a short TTL
   (e.g. 10 s) inside `get_opencode_session_tokens`.

5. **Add a `model` column to `session_history`** — there is no way today to attribute
   cost to a specific model. The current model is decided per step (plan / build /
   review) in `demetra/settings.py:111`. A new Alembic migration
   (`add_session_history_model_column`) and matching field on
   `demetra/library/models.py:57` plus `demetra/services/database.py:491` would unlock
   per-model cost dashboards.

6. **Investigate `cache_write_tokens = 0` everywhere** — the column exists in
   `demetra/library/tables.py:108` but no row in the sample has a non-zero value.
   Either the opencode export schema is different for these models, or the key has
   moved. Inspect a live `opencode export` payload and adjust the parser at
   `demetra/services/opencode.py:184`.

7. **Backfill the four NULL-only sessions** — if the worktrees still exist somewhere,
   re-run the export; otherwise tag the rows with a sentinel so the stats stop being
   skewed.

8. **Truncate long plan output before Groq summarisation** — `extract_plan` at
   `demetra/services/groq.py:105` ships the full plan output. Capping the input to the
   last ~8 k tokens before the LLM call would cap cost on long planning iterations.

## Open questions

- **"Compaction never fires" is wrong** — git history shows `check_and_compact_context`
  was added in `efbf4c7` (2026-07-06) and its only caller was commented out in
  `5f8e428` (2026-07-21, MNT-145). So compaction was *live* for most of the sampled
  period. The "0 shrink events" query is also invalid: `length` is a cumulative
  session counter and cannot decrease even when `/compact` succeeds. See the full
  correction in [[2026-07-23-session-tokens-audit-revalidation]].
- **"NULL rows are caused by cleanup ordering" is wrong** — the NULL rows are
  pre-fix pipe-truncation cases. All 48 NULL rows are timestamped before
  `f96b07f` (2026-07-17 00:08 +03, "Fix session tokens countes"); zero NULLs since.
  Documented in [[2026-07-16-session-history-tokens-null]].
- `cache_write_tokens` is 0 in the sample **and** in a live `opencode export` payload
  measured on 2026-07-16 — likely genuine opencode behaviour for these models.
- Does `opencode export` expose per-message token usage? Needed for a "current context"
  metric that would actually make the threshold meaningful.

---

## Follow-ups

- Read [[2026-07-23-session-tokens-audit-revalidation]] before implementing any of the
  recommendations above — it changes recommendations 1, 3, 4, and 7.
- Coordinate with the `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md` implementation plan.

## References

- Related: [[2026-07-16-session-history-tokens-null]], [[2026-07-23-session-tokens-audit-revalidation]]
- Root doc: `wiki/audits/2026-07-23-session-tokens/RESULT.md`
