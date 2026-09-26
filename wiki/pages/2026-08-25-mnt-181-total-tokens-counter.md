---
title: "MNT-181: Total tokens counter"
date: 2026-08-25
type: implementation
status: resolved
session_id: "-"
services: [api, sessions, react]
branch: mnt-181-total-tokens-counter
tickets: [MNT-181, MNT-84, MNT-59]
tags: [session-history, tokens, react, api, frontend, sessions, title, sidebar, websocket]
related:
- 2026-07-23-session-history-modal.md
- 2026-07-23-session-tokens-audit-revalidation.md
- 2026-05-22-task-title-session-listing.md
- 2026-07-16-fix-step-status-review-findings.md
- 2026-07-16-session-history-tokens-null.md
---

# MNT-181: Total tokens counter

## TL;DR

Added a session-wide **Total Tokens** summary to the history modal. `GET /api/v1/sessions/{task_id}/history` now returns `{"total": {...}, "history": [...]}` via `_compute_total_tokens` in `demetra/api/sessions.py` (sums input/output/reasoning/cache read/write, `None`→0, excludes `context_tokens`, falls back to `row.length` for legacy null rows). React modal renders breakdown grid + grand total. Merged via PR #101.

## Overview

| Layer | Change |
| ----- | ------ |
| Backend | `GET /api/v1/sessions/{task_id}/history` → `{ total, history }`; `_compute_total_tokens()` |
| Frontend API | `SessionHistoryResponse`, `SessionTokenTotals`, `EMPTY_TOKEN_TOTALS`; `getSessionHistory` wrapper |
| UI | `TotalTokensBlock` in `SessionHistory.tsx`; `.session-history-totals*` CSS in `App.css` |
| Tests | 4 API tests; extended `SessionHistory.test.tsx`/`SessionArtifacts.test.tsx` |

Extends [[2026-07-23-session-history-modal]].

## Backend

`demetra/api/sessions.py`:
```python
rows = await get_session_history(session_id=session_id)
return {"total": _compute_total_tokens(rows=rows), "history": [_serialize_history_row(row=r) for r in rows]}
```
Rules: sum `input_tokens`/`output_tokens`/`reasoning_tokens`/`cache_read_tokens`/`cache_write_tokens` (`None`→0); `context_tokens` excluded (per-step snapshot, see [[2026-07-23-session-tokens-audit-revalidation]]); `length` grand total from summed token fields when present, else sum `row.length`. `_serialize_history_row` also exposes `context_tokens`/`model`.

## Frontend API

`react/src/services/api.ts` — `SessionTokenTotals` (`length`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`), `SessionHistoryResponse` (`total`+`history`). 404 → `{ total: EMPTY_TOKEN_TOTALS, history: [] }`.

## Modal UI

`react/src/components/SessionHistory.tsx` — `TotalTokensBlock` below timeline when `entries.length>0`; cards show `context_tokens`/`model` when present; `toLocaleString()`; title `Session History [BETA]`; `<time title={entry.created_at}>`. `SessionArtifacts.tsx` stores full response, passes `total={historyData?.total ?? EMPTY_TOKEN_TOTALS}`.

## CSS

`react/src/App.css` — `.session-history-totals`, `.session-history-totals-header`, `.session-history-totals-grid`, `.session-history-totals-grand` (bordered summary, warp tokens).

## Test Results

Backend `tests/test_api.py:TestSessionHistoryEndpoint`: `test_returns_total_and_history`, `test_total_treats_null_tokens_as_zero`, `test_total_for_empty_history_is_all_zeros`, `test_total_sums_length_independently`. Frontend: `SessionHistory.test.tsx` (totals block), `SessionArtifacts.test.tsx` (mock `{ total, history }`).

## Source — [[2026-05-22-task-title-session-listing]]

Session list title fallback (`task_title`/`custom name` → truncated `session_id`, `GET /api/v1/sessions?step=...` see [[2026-07-16-fix-step-status-review-findings]]) — still in effect.

## Follow-ups

- None.

## Consistency fix (2026-09-01)

- Added `2026-07-16-fix-step-status-review-findings.md` to `related`.

## Consistency fix (2026-09-02)

- Quoted `session_id: -` → `"-"`.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-23-session-history-modal]], [[2026-07-16-session-history-tokens-null]], [[2026-07-23-session-tokens-audit-revalidation]]
- External: https://github.com/manti-by/demetra/pull/101, [MNT-181](https://linear.app/mnt/issue/MNT-181)
