# Session History & Token Consumption Audit

> **Revalidated again 2026-07-23** against the working tree, Git history, a live
> OpenCode 1.18.4 export, and the Odin DB (`192.168.1.100:5432`). The 192-row database
> sample is unchanged and all published aggregates reproduce exactly. Additional
> details were corrected below: 144 post-fix rows (not 136), the exact per-message token
> path, model-specific cache-write behavior, the short-TTL/billable-token claims, and
> the limits of a single `model` column on cumulative snapshots.

## Summary

Demetra records an `opencode` session's token usage into the `session_history` table at
each workflow step (`plan`, `build`, `completed`, `failed`, `awaiting_input`). Tokens are
extracted via `opencode export <session_id>`, summed into a single `length` column, and
compared against `CONTEXT_COMPACTION_THRESHOLD` (default 100 000) to decide whether
`/compact` should run.

Key facts established by the revalidation:

- **`length` is a cumulative session counter, not the current context size.** Build rows
  reach 40 M tokens — no model context is that large. The value monotonically grows for
  the life of a session, so comparing it against a 100k threshold means every session
  "exceeds" the threshold from its first few messages onward, forever.
- **The current-context metric is available.** A live OpenCode 1.18.4 export has
  `messages[].info.tokens`; the latest assistant message's
  `tokens.input + tokens.cache.read` is the context usage OpenCode itself reports. In the
  inspected session, top-level `info.tokens` exactly matched the sum of all 58 assistant
  messages (4,191,230 total), while the latest context was only 95,839 tokens.
- **Compaction was live for most of the sampled period.** `check_and_compact_context`
  was added in `efbf4c7` (MNT-122) and only disabled on **2026-07-21 14:12** by
  `5f8e428` "MNT-145: Disable context compaction" (`demetra/workflows/build.py:77`).
  All 69 build rows with usable lengths exceed the threshold, so the code attempted
  `/compact` on every one — which is the likely reason it was disabled, and why simply
  uncommenting the call is not the fix.
- **The "0 shrink events" query proves nothing about compaction.** A cumulative counter
  cannot decrease even when `/compact` succeeds, so the absence of shrinking rows is
  expected regardless of whether compaction ran.
- **The NULL-length rows are a solved problem.** All 48 NULL rows predate the
  pipe-truncation fix (`run_command_to_file`, commit `f96b07f`, 2026-07-17 00:08 +03) —
  44 rows on 07-16 and 4 rows between 00:01–00:02 on 07-17. Zero NULLs in the 144 rows
  recorded since. Root cause is documented in
  [`wiki/pages/2026-07-16-session-history-tokens-null.md`](wiki/pages/2026-07-16-session-history-tokens-null.md).
- Cache reads dominate the totals (1.86 B cached vs 71.6 M input) and
  `cache_write_tokens` is 0 in every row — including the live payload measured on Odin
  during the 07-16 debugging session. The parser path is correct, but zero writes are
  model/provider-specific rather than universal: the local OpenCode store contains 699
  non-zero cache-write messages among 14,408 assistant messages, primarily on the
  `qwen3.7-max` and `qwen3.7-plus` models.

Verification used SELECT-only access to the Odin database. The new export inspection
ran locally, not on Odin. Without server shell/log access, this pass cannot prove whether
individual `/compact` commands succeeded or independently confirm that historical
worktrees no longer exist.

---

## Recommendations

1. **Fix the compaction metric before re-enabling compaction.** The threshold check in
   `check_and_compact_context` ([`demetra/workflows/build.py:19`](demetra/workflows/build.py))
   must compare the **current context size** against `CONTEXT_COMPACTION_THRESHOLD`, not
   the cumulative session total. The live export confirms the exact source is the last
   assistant entry in `messages[]`: `message.info.tokens.input +
   message.info.tokens.cache.read`. Excluding cache reads from the cumulative sum is
   *not* sufficient: `input + output + reasoning` is also monotonically growing.

2. **Re-enable `check_and_compact_context`** (uncomment
   [`demetra/workflows/build.py:77`](demetra/workflows/build.py), resolving the MNT-145
   TODO) — but only after recommendation 1 lands, otherwise `/compact` fires on every
   build iteration again.

3. **Keep the token breakdown; calculate cost from model-specific rates.**
   `TokenUsage.total` ([`demetra/library/models.py:53`](demetra/library/models.py)) is a
   valid raw cumulative measure. Do not label `input + output + reasoning` as
   `billable`: OpenCode's cost calculation prices input, output/reasoning, cache reads,
   and cache writes separately, and cached tokens are not universally free. Add the
   model dimension first, then calculate monetary cost with the applicable rate card.

4. **Persist model-aware usage, not only a step-level `model` label.** A Demetra session
   starts with `OPENCODE["plan_model"]` and is resumed with
   `OPENCODE["build_model"]`, while every `session_history` row stores cumulative usage
   across both. Labeling a completed snapshot as the build model would therefore
   misattribute plan tokens. The confirmed `messages[].info` payload includes
   `providerID`, `modelID`, and per-message tokens; persist per-model counters or deltas
   from those messages. A single nullable `model` column may still be useful as workflow
   metadata, but it does not unlock accurate cost attribution by itself.

5. **Keep `cache_write_tokens`.** The parser's `info.tokens.cache.write` path is correct,
   and both the Odin sample and a new 58-assistant-message `minimax-m3` export report 0.
   A broader local OpenCode query found 699 non-zero writes among 14,408 assistant
   messages, however, proving the field is meaningful for models/providers that expose
   cache creation. Once `model` is recorded, distinguish genuine zero-write model usage
   from missing data.

6. **Truncate long plan output before Groq summarisation** — `extract_plan` at
   [`demetra/services/groq.py:101`](demetra/services/groq.py) ships the full plan output
   to `llama-3.1-8b-instant`. Capping the input to the last ~8 k tokens caps cost and
   avoids hard failures against the model's 131k context on long planning iterations.

### Dropped from the original audit

- ~~"Record the row before cleanup / keep the worktree until persisted"~~ — **refuted**:
  recording already happens *before* `git_cleanup` (`cleanup.py:95` vs `cleanup.py:103`,
  and the `completed` row is written in `commit_and_push` which runs before
  `cleanup_workflow`). This ordering has been the same in every committed version. The
  NULL rows were caused by the 64 KB pipe truncation, fixed 2026-07-17.
- ~~"Cache the export per `session_id` with a ~10 s TTL"~~ — **low impact, not zero
  impact**: build iterations are generally minutes apart, but 11 of 174 adjacent
  same-session observations in the Odin sample occurred within 10 seconds. A cache could
  therefore hit about 6% of observed transitions, mostly `plan` to immediate cleanup.
  That is not enough benefit to prioritize cache invalidation and stale-snapshot risks.
- ~~"Backfill the four NULL-only sessions / tag with `length = -1`"~~ — the sessions
  predate the pipe-truncation fix and cannot be reconstructed from the database alone;
  the prior investigation reports their worktrees are gone, which database access cannot
  revalidate. A `-1` sentinel would *skew* aggregates (SQL already ignores NULLs), so
  leave the rows as-is.

---

## Corrections vs. the original audit (2026-07-23 revalidation)

| Original claim | Verdict | Evidence |
|---|---|---|
| Compaction "never actually fires — its only caller is commented out" | **Misleading** | Enabled `efbf4c7` → disabled `5f8e428` on 2026-07-21 14:12; most of the 192 sampled rows were recorded while it was live |
| 0 shrink events ⇒ compaction not happening | **Invalid inference** | `length` is cumulative and cannot shrink; the query cannot detect compaction either way |
| NULL rows caused by recording after `git_cleanup` removed the worktree | **Refuted** | Recording precedes `git_cleanup` in all committed versions; all 48 NULLs predate the `f96b07f` pipe-truncation fix (2026-07-17 00:08 +03); 0 NULLs since |
| `extract_plan` at `groq.py:90` | **Wrong line** | `groq.py:101` (`:90` is inside `process_text_with_groq`) |
| `record_session_step_history` at `database.py:929` | **Shifted** | The definition starts at `database.py:939` in the current working tree (`usage` is line 942) |
| All DB statistics (totals, per-step distribution, thresholds, NULL sessions, daily volume) | **Confirmed** | Re-queried Odin 2026-07-23; every figure reproduced (build avg is 16.8 M, originally rounded to 16.7 M) |
| 136 rows recorded after the pipe fix | **Wrong count** | 144 rows were recorded at or after `f96b07f`; all 144 have non-NULL lengths |
| A 10 s export cache would never hit | **Refuted** | 11 / 174 adjacent same-session observations are no more than 10 seconds apart; still too few to justify prioritizing a cache |
| `input + output + reasoning` is a billable-token view | **Refuted** | OpenCode prices cache reads/writes separately by model; excluding them can understate cost |
| `cache_write=0` may be a parser/schema problem | **Refuted** | The path is correct; writes are zero for the sampled Odin/minimax data but non-zero for 699 local assistant messages on other models |
| One `model` column enables per-model costs | **Refuted** | Rows are cumulative across the plan and build models; accurate attribution requires per-message model usage or interval deltas |

---

## How the current flow works

### Token extraction

[`demetra/services/opencode.py:142`](demetra/services/opencode.py) — `get_opencode_session_tokens`
runs `opencode export <session_id>` (via [`demetra/services/subprocess.py:47`](demetra/services/subprocess.py)
to avoid the 64 KB pipe buffer truncation) and reads
`info.tokens.{input,output,reasoning}` plus `info.tokens.cache.{read,write}`. Each value
goes through `non_negative_int` at
[`demetra/services/utils.py:119`](demetra/services/utils.py). If any of `input`,
`output`, or `reasoning` is missing or negative, the function returns `None` and the
row is recorded with all token columns `NULL`.

### Length calculation

[`demetra/library/models.py:53`](demetra/library/models.py) — `TokenUsage.total` =
`input + output + reasoning + cache_read + cache_write`. This is what
`get_opencode_session_length` returns and what gets stored in the `length` column.
**These are cumulative session totals** — see Summary.

### Storage

[`demetra/services/database.py:939`](demetra/services/database.py) —
`record_session_step_history` writes one `session_history` row per call. The schema is
defined in [`demetra/library/tables.py:97`](demetra/library/tables.py) and the
`SessionHistory` dataclass in [`demetra/library/models.py:58`](demetra/library/models.py).
Two Alembic migrations create the table and add the token columns:
[`migrations/versions/f1a2b3c4d5e6_add_session_history_table.py`](migrations/versions/f1a2b3c4d5e6_add_session_history_table.py)
and
[`migrations/versions/a2b3c4d5e6f7_add_session_history_token_columns.py`](migrations/versions/a2b3c4d5e6f7_add_session_history_token_columns.py).

### Recording call sites

| Step | File | Note |
|---|---|---|
| `plan` | [`demetra/workflows/plan.py:82`](demetra/workflows/plan.py) | inside `run_plan_step`, after session is saved |
| `build` | [`demetra/workflows/build.py:33`](demetra/workflows/build.py) | inside `check_and_compact_context`, disabled since 2026-07-21 (`build.py:77`, MNT-145) |
| `completed` | [`demetra/workflows/cleanup.py:69`](demetra/workflows/cleanup.py) | in `commit_and_push`, *before* `cleanup_workflow` / `git_cleanup` |
| `failed` | [`demetra/workflows/cleanup.py:95`](demetra/workflows/cleanup.py) | in `cleanup_workflow`, *before* `git_cleanup` at `cleanup.py:103` |
| `awaiting_input` | [`demetra/workflows/cleanup.py:95`](demetra/workflows/cleanup.py) | same failure path with `failure_step="awaiting_input"` from `main.py:100` |

### Compaction

[`demetra/workflows/build.py:19`](demetra/workflows/build.py) — `check_and_compact_context`
reads the current usage, records it, and shells out to `opencode_compact_session`
([`demetra/services/opencode.py:204`](demetra/services/opencode.py)) when
`length > CONTEXT_COMPACTION_THRESHOLD` ([`demetra/settings.py:40`](demetra/settings.py),
default 100 000). The only caller was disabled on 2026-07-21 by `5f8e428`
(MNT-145) at `build.py:77`.

---

## Statistical findings (Odin DB, 192 rows / 18 sessions)

Source DB: `192.168.1.100:5432` (server address confirmed by PostgreSQL; timezone
`Europe/Minsk`). Re-verified again 2026-07-23 with read-only queries — all figures below
reproduced exactly.

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

Note: `length` is cumulative, so "over threshold" reflects total session usage, not
context pressure at that moment.

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

All four predate the pipe-truncation fix (`f96b07f`, committed 2026-07-17 00:08 +03):

```text
ses_093a105c8ffeAfoNF0eKjA9XXq   4 rows
ses_09416fcdeffeegOO9AxgsFoN0i   12 rows
ses_094e1f9ecffeNpkybkydRRlPYh   13 rows
ses_0937edfd8ffe9k1Y5s9ekQGSI2   9 rows
```

NULL rows by day: 44 on 2026-07-16, 4 on 2026-07-17 (00:01–00:02 +03), 0 afterwards.
The last NULL is at 00:02:34; all 144 rows at or after the 00:08:58 fix commit have
non-NULL lengths (the first is at 00:28:31).

### Compaction evidence

Querying for sessions where a later row's `length` is smaller than an earlier row's
returns **0 rows** — but since `length` is a cumulative counter this is expected and
says nothing about whether `/compact` succeeded. Source and row evidence show that the
command was attempted for every build row with a usable length until MNT-145 disabled
the caller on 2026-07-21.

All 69 build rows with a non-NULL length exceed 100 k; the remaining 31 build rows are
the pre-fix NULL cases. Seven build rows were recorded between the disable commit at
14:12 and 14:44, consistent with deployment lag or an already-running old process; the
commit timestamp is therefore a source-history cutoff, not an exact production cutoff.

### Daily volume

| Date | Rows | Sum length |
|---|---|---|
| 2026-07-16 | 44 | 0 (all NULL — pre-fix) |
| 2026-07-17 | 12 | 54.9 M |
| 2026-07-20 | 96 | 1 206.6 M |
| 2026-07-21 | 32 | 578.0 M |
| 2026-07-22 | 8 | 105.6 M |
