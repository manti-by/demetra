---
title:              Session History Modal
date:               2026-07-23
type:               implementation
status:             resolved
session_id:         "-"
services:           [api, sessions, react]
branch:             "-"
tickets:            []
tags:               [frontend, modal, session-history, react, api]
related:
- 2026-08-25-mnt-181-total-tokens-counter.md
- 2026-07-22-react-frontend-template-warp.md
- 2026-07-16-session-history-tokens-null.md
---

# Session History Modal

## TL;DR

Added a "View History" button in `SessionArtifacts` that opens a modal timeline of `session_history` rows (step, timestamp, token breakdown). Backend was a thin `GET /api/v1/sessions/{task_id}/history` resolving `task_id`→`session_id`; rest is React + CSS. 9 files, ~220 lines, all tests pass.

## Overview

| Layer | Implemented |
|-------|-------------|
| Backend | `get_session_id_by_task_id` + history endpoint (404 when `session_id` null) |
| API client | `getSessionHistory(taskId)` + `SessionHistoryEntry` type (404→`[]`) |
| Component | `SessionHistory.tsx` (112 lines, `memo`) mirroring build-plan modal |
| Wiring | "View History" link in `SessionArtifacts.tsx` with `hasHistory` guard |
| Styling | `~70` lines `.session-history-*` in `App.css` (warp tokens) |
| Tests | 7 unit + 4 integration + 4 API + 3 DB tests |

## Step 1 — Backend: `get_session_id_by_task_id`

**`demetra/services/database.py`** — `select(sessions.c.session_id).where(task_id==…)` → `str | None` (None when no row or `session_id` null).

## Step 2 — History endpoint

**`demetra/api/sessions.py`** — `GET /{task_id}/history` with `TASK_ID_PATTERN` validation, cookie auth, `_serialize_history_row` → ISO `created_at`, 404 when no session, 401 without auth.

## Step 3 — Frontend API client

**`react/src/services/api.ts`** — `SessionHistoryEntry` (id, session_id, step, created_at, length, input/output/reasoning/cache_read/cache_write), `getSessionHistory` via `fetch` with `credentials:'include'`, 404→`[]`.

## Step 4 — `SessionHistory` component

**`react/src/components/SessionHistory.tsx`** (112 lines) — props `entries/isOpen/onClose/isLoading/error`; states: closed/loading/error/empty/timeline. Card: step (mono, uppercase, accent) + `formatRelativeTime` header, `dl` grid of tokens (hidden when all null). Close via button + overlay. `memo` wrapped.

## Step 5 — Wire into `SessionArtifacts`

- Added `historyOpen/Loading/Error/Entries` state + async `openHistory` (open→loading→fetch→populate/error).
- `hasHistory = !!session.session_id` guard; early return now includes `hasHistory` so link renders even without other artifacts.
- Clock SVG link `<a class="session-artifacts-link">` when `hasHistory`; renders `<SessionHistory>` alongside build-plan modal. No `App.tsx` changes needed.

## Step 6 — CSS

**`react/src/App.css`** — reusing shared `.modal-*` classes:

| Class | Purpose |
|-------|---------|
| `.session-history-modal` | `max-width:720px` |
| `.session-history-timeline` | vertical flex, `gap:0.75rem` |
| `.session-history-card` | bordered `surface-2` card |
| `.session-history-step` | mono uppercase accent |
| `.session-history-time` | `0.7rem` tertiary |
| `.session-history-tokens` | 3-col grid |
| `.session-history-empty/error` | centered placeholder |

No new CSS variables.

## Step 7 — Tests

- **API** (`tests/test_api.py` `TestSessionHistoryEndpoint`): 401 no/invalid token, 404 when no session, returns rows with structure.
- **DB** (`tests/test_database.py` `TestGetSessionIdByTaskId`): known task, unknown task, empty `session_id`.
- **Frontend** `SessionHistory.test.tsx` (7 cases): closed→nothing, loading spinner, empty, one card per entry, token dl conditional, close button + overlay.
- **Frontend** `SessionArtifacts.test.tsx` (4 new): renders link when `session_id`, opens modal on click, no link when empty, link with only `session_id`.

## Test Results

`ruff`, `ty` clean; `pytest` 480 passed; `react` build + 33 vitest passed.

## Open questions

- Paginate timeline vs render all (~10 rows typical; future per-LLM-call granularity may matter).
- Absolute time on hover (`title={created_at}`) — cheap, recommended yes.

## Follow-ups

- Add Escape handler to history modal.
- ~~Add `title={created_at}` on `<time>`~~ Done in MNT-181 — see [[2026-08-25-mnt-181-total-tokens-counter]].
- Verify `record_session_history` coverage: `SELECT DISTINCT step FROM session_history`.

> **Consistency note (2026-08-25):** MNT-181 (PR #101) changed endpoint to `{"total":{…},"history":[…]}`, added Total Tokens summary, `context_tokens`/`model` fields. DB helpers → `demetra/services/persistence/database.py`. See [[2026-08-25-mnt-181-total-tokens-counter]].

> **Status update (2026-08-27):** Auth now `user: UserResponse = Depends(get_current_user_dep)` not raw `auth_token` Cookie; `get_session_id_by_task_id(task_id, user_id)` scopes by user (MNT-156). Behavior unchanged.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- [[2026-07-22-react-frontend-template-warp]] — warp CSS variables
- [[2026-07-16-session-history-tokens-null]] — why tokens can be null
- [[2026-08-25-mnt-181-total-tokens-counter]] — total tokens + response-shape change
- `demetra/services/database.py:535` — `get_session_history` · `demetra/library/tables.py:97` — `session_history` · `react/src/components/SessionArtifacts.tsx:111-134` — build-plan modal pattern
