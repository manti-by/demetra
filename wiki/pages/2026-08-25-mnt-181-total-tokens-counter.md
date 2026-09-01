---
title: "MNT-181: Total tokens counter"
date: 2026-08-25
type: implementation
status: resolved
session_id: -
services: [api, sessions, react]
branch: mnt-181-total-tokens-counter
tickets: [MNT-181, MNT-84, MNT-59]
tags: [session-history, tokens, react, api, frontend, sessions, title, sidebar, websocket]
related: [2026-07-23-session-history-modal.md, 2026-07-23-session-tokens-audit-revalidation.md, 2026-07-16-session-history-tokens-null.md, 2026-05-22-task-title-session-listing.md, 2026-07-16-fix-step-status-review-findings.md]
---

# MNT-181: Total tokens counter

## TL;DR

Extended the session history modal with a session-wide **Total Tokens** summary block. The history endpoint now returns `{"total": {...}, "history": [...]}` instead of a bare row list: `_compute_total_tokens` in `demetra/api/sessions.py` sums input/output/reasoning/cache read/cache write across all history rows (treating `None` as zero, excluding per-step `context_tokens` from the aggregate, and falling back to legacy `row.length` when every token field is null). The React modal renders a breakdown grid plus a grand total below the per-step timeline; API and component tests cover empty history, null-token rows, and independent length summation. Merged via PR #101.

---

## Overview

| Layer | Change |
| ----- | ------ |
| Backend | `GET /api/v1/sessions/{task_id}/history` response shape → `{ total, history }`; new `_compute_total_tokens()` |
| Frontend API | `SessionHistoryResponse`, `SessionTokenTotals`, `EMPTY_TOKEN_TOTALS`; `getSessionHistory` returns the wrapper object |
| UI | `TotalTokensBlock` in `SessionHistory.tsx`; `.session-history-totals*` CSS in `App.css` |
| Tests | 4 new API tests for totals; extended `SessionHistory.test.tsx` and `SessionArtifacts.test.tsx` |

Builds on the history modal from [[2026-07-23-session-history-modal]].

---

## Step 1 — Backend totals computation

**File:** `demetra/api/sessions.py`

The endpoint now returns a dict with `total` and `history` keys:

```python
rows = await get_session_history(session_id=session_id)
return {"total": _compute_total_tokens(rows=rows), "history": [_serialize_history_row(row=r) for r in rows]}
```

`_compute_total_tokens` rules:

- Sum `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens` across rows; `None` counts as 0.
- **`context_tokens` is excluded** — it is a per-step context-window snapshot, not a usage counter (see [[2026-07-23-session-tokens-audit-revalidation]]).
- **`length` grand total** is derived from the summed token fields when any token field is present on a row; for legacy rows where every token field is `None`, fall back to summing `row.length` instead.

`_serialize_history_row` also exposes `context_tokens` and `model` per row (fields added after the original modal shipped).

---

## Step 2 — Frontend API client

**File:** `react/src/services/api.ts`

```typescript
export interface SessionTokenTotals {
  length: number;
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
}

export interface SessionHistoryResponse {
  total: SessionTokenTotals;
  history: SessionHistoryEntry[];
}
```

404 responses return `{ total: EMPTY_TOKEN_TOTALS, history: [] }` (not a bare empty array).

---

## Step 3 — Modal UI

**File:** `react/src/components/SessionHistory.tsx`

- New `TotalTokensBlock` component renders below the timeline when `entries.length > 0`.
- Per-card display now conditionally shows `context_tokens` and `model` when present; numeric fields use `toLocaleString()`.
- Modal title reads **Session History [BETA]**.
- `<time>` elements include `title={entry.created_at}` (one of the follow-ups from [[2026-07-23-session-history-modal]]).

**File:** `react/src/components/SessionArtifacts.tsx`

Stores the full `SessionHistoryResponse` and passes `total={historyData?.total ?? EMPTY_TOKEN_TOTALS}` to the modal.

---

## Step 4 — CSS

**File:** `react/src/App.css`

Added `.session-history-totals`, `.session-history-totals-header`, `.session-history-totals-grid`, and `.session-history-totals-grand` — bordered summary block below the timeline, reusing warp theme tokens.

---

## Test Results

Backend (`tests/test_api.py` — `TestSessionHistoryEndpoint`):

- `test_returns_total_and_history` — response keys and summed totals match mock rows
- `test_total_treats_null_tokens_as_zero` — null fields contribute 0
- `test_total_for_empty_history_is_all_zeros`
- `test_total_sums_length_independently` — legacy rows with only `length` set

Frontend: extended `SessionHistory.test.tsx` (totals block presence/absence) and `SessionArtifacts.test.tsx` (mock returns `{ total, history }`).

---

## Source — [[2026-05-22-task-title-session-listing]]

Session list shows task title with fallback to truncated id. Originally decided in [[2026-05-22-task-title-session-listing]] on 2026-05-22 (MNT-84): `GET /api/v1/sessions` now renders `task_title`/`custom name` with truncated `session_id` fallback; the filter param was renamed `status` → `step` (`GET /api/v1/sessions?step=...`, see [[2026-07-16-fix-step-status-review-findings]]). Still in effect — React `SessionArtifacts`/`SessionSidebar` rely on it. Conventions: session display uses `custom name` when available, fallback to truncated id; API auth error messaging improved as part of same session.

## Follow-ups

- None from this session.

## Consistency fix (2026-09-01)

- Added `2026-07-16-fix-step-status-review-findings.md` to `related` frontmatter to mirror body link `[[2026-07-16-fix-step-status-review-findings]]`.

## References

- Related: [[2026-07-23-session-history-modal]] (original modal — API shape superseded here)
- Related: [[2026-07-16-session-history-tokens-null]] (why per-row token fields can be null)
- Related: [[2026-07-23-session-tokens-audit-revalidation]] (`context_tokens` vs usage counters)
- External: https://github.com/manti-by/demetra/pull/101, [MNT-181](https://linear.app/mnt/issue/MNT-181)
