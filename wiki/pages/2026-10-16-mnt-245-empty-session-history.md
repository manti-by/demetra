---
title: "MNT-245: Empty session history"
date: 2026-10-16
type: investigation
status: resolved
session_id: "-"
services: [persistence, workflows, api, react]
branch: "-"
tickets: [MNT-245, MNT-251, MNT-246, MNT-228, MNT-181]
tags: [session-history, empty-rows, tokens, research, validate, review, cumulative]
related: [2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-opencode-v2-session-token-accounting.md, 2026-09-30-mnt-228-intermediate-history-states.md, 2026-08-25-mnt-181-total-tokens-counter.md, 2026-07-23-session-history-modal.md]
---

# MNT-245: Empty session history

## TL;DR

Research into why `validate`, `review` and `research` steps render as empty cards in the session-history timeline. Root cause: two independent writers — `update_session_step` writes a guaranteed-empty step row on every transition, while token rows come from a separate path that only `plan`/`build`/`completed`/`failed` ever called — and validate/review/research run in throwaway sessions that are never persisted. All of it is fixed by [[2026-10-16-mnt-251-session-attribution-accounting]]: step rows and invocation rows are now distinct `kind`s, every agent step records an exact-delta invocation row, and totals sum only `kind='invocation'`.

---

## Net effect

The "empty card" symptom was structural, not a data-loss accident: those steps were *incapable* of carrying token data because they ran in unpersisted sessions and had no recording call. It also closed the long-open follow-up in [[2026-07-23-session-history-modal]] (`SELECT DISTINCT step FROM session_history`).

## Root causes

- **Two writers, only some record tokens** — `update_session_step(..., session_id=...)` inserted a step-only row on *every* transition (build, validate, review, lint/test, wiki, push, research); the token-writing path was called from only `plan`, `build`, `completed`, `failed`. Validate/review/research had no token call at all.
- **Throwaway sessions** — `opencode_review_agent` / `opencode_validate_agent` / `opencode_research_agent` called `run_opencode_agent` without `session_id`, so each spawned a new session never persisted to `sessions.session_id` and never readable by export.
- **Duplicate rows per step** — the step-start row (empty) and the step-end token row were both written for build/plan.
- **Cumulative inflation** — `get_opencode_session_tokens` read the cumulative `info.tokens`, and `_compute_total_tokens` summed every row, so the same tokens were counted many times.

## Corrections (2026-10-16)

- "`record_session_step_history` is called from only three sites" is **wrong — there are four** (`plan.py:149`, `build.py:39`, `cleanup.py:127` and `cleanup.py:172`). MNT-246 §b states it correctly.
- "Session totals are inflated" was **stale** at the time of this correction: production was on v2 where the top-level `export` subcommand no longer existed, so `get_opencode_session_tokens` returned `None` and columns were **NULL, not inflated**. The inflation returned once the export path was fixed, which is why the delta model still had to ship.
- Two tech requirements were **superseded**: the delta cursor lives on `agent_sessions` (not "diff against the previous row", which breaks on a failed export), and review needs one session per `(round, model)` (not one threaded id) because three models run concurrently into the same directory.

## How MNT-251 resolves it

- `kind='step'` rows (no tokens) and `kind='invocation'` rows (exact deltas) are distinct; `update_session_step` no longer writes history, `record_session_step(task_id, step)` does.
- Every agent step — including research, resolve, merge, rebase, review_fixes and review per `(round, model)` — records an invocation row.
- `_compute_total_tokens` sums only `kind='invocation'`; the legacy `row.length` fallback is dropped.
- React renders from the explicit `kind` field instead of null-sniffing.

## Follow-ups

- None — the acceptance criteria ("no empty rows for agent steps", "no duplicate step entries per agent run", "totals equal the final cumulative reading") are covered by MNT-251.

## References

- Related: [[2026-10-16-mnt-251-session-attribution-accounting]] — the implementation
- Related: [[2026-10-16-opencode-v2-session-token-accounting]] — the v2 ground truth that corrected the inflation claim
- Related: [[2026-09-30-mnt-228-intermediate-history-states]] — the step-row writer this supersedes
- Related: [[2026-08-25-mnt-181-total-tokens-counter]] — the total this re-points at `kind='invocation'`
- Related: [[2026-07-23-session-history-modal]] — the endpoint and the follow-up this closes
- External: https://linear.app/mnt/issue/MNT-245
