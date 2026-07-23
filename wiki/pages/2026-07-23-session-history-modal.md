---
title:              Session History Modal
date:               2026-07-23
type:               implementation
status:             resolved
session_id:         -
services:           [api, sessions, react]
branch:             -
tickets:            []
tags:               [frontend, modal, session-history, react, api]
related:            [2026-07-22-react-frontend-template-warp.md, 2026-07-16-session-history-tokens-null.md]
---

# Session History Modal

## TL;DR

Add a "View History" button next to "View Build Plan" in `SessionArtifacts` that opens a modal showing the per-step session history rows (step name, timestamp, token-usage breakdown) as a vertical timeline of cards. The `session_history` table and `get_session_history()` already exist on the backend; the only backend work is a thin `GET /api/v1/sessions/{task_id}/history` endpoint that resolves `task_id` → `session_id` and returns the rows. All other work is React + CSS.

Implemented in full: 9 files changed, ~220 lines added. All tests pass.

---

## Overview

| Layer      | Build Plan                                                                                   | Implemented                                          |
| ---------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Backend    | New endpoint `GET /api/v1/sessions/{task_id}/history`; 404 when `session_id` is null        | Done + `get_session_id_by_task_id` in database       |
| API client | Add `getSessionHistory(taskId)` + `SessionHistoryEntry` TS type                              | Done                                                 |
| Component  | New `SessionHistory.tsx` mirroring the build-plan modal pattern                              | Done (112 lines, memo wrapped)                       |
| Wiring     | Add "View History" link in `SessionArtifacts.tsx`; share modal state with the build-plan     | Done + `hasHistory` guard in early-return            |
| Styling    | Add `.session-history-*` blocks to `App.css`                                                 | Done (~70 lines, warp theme tokens)                  |
| Tests      | Vitest tests for the new component; FE build/lint; backend API + DB tests                    | Done: 7 unit + 4 integration + 4 API + 3 DB tests    |

---

## Step 1 — Backend: `get_session_id_by_task_id`

**File:** `demetra/services/database.py`

New function to resolve a `task_id` (e.g. `TASK-123`) to the opaque `opencode_session_id` stored in the `sessions` table:

```python
async def get_session_id_by_task_id(task_id: str) -> str | None:
    async with get_connection() as connection:
        result = await connection.execute(
            select(sessions.c.session_id)
            .where(sessions.c.task_id == task_id)
        )
        row = result.fetchone()
    if not row or not row.session_id:
        return None
    return row.session_id
```

Returns `None` when the task has no session yet (no rows, or `session_id` is null).

---

## Step 2 — Backend: history endpoint

**File:** `demetra/api/sessions.py`

```python
@router.get("/{task_id}/history")
async def get_session_history_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    auth_token: str | None = Cookie(default=None),
) -> list[dict]:
```

Authentication uses the same cookie-based flow as other endpoints. Returns serialized `SessionHistory` rows in `created_at` order; 404 when `session_id` is null; 401 without auth.

The `_serialize_history_row` helper converts the `SessionHistory` dataclass to a flat dict with ISO-format `created_at`:

```python
def _serialize_history_row(row: SessionHistory) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "step": row.step,
        "length": row.length,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "reasoning_tokens": row.reasoning_tokens,
        "cache_read_tokens": row.cache_read_tokens,
        "cache_write_tokens": row.cache_write_tokens,
        "created_at": row.created_at,
    }
```

---

## Step 3 — Frontend API client

**File:** `react/src/services/api.ts`

Added `SessionHistoryEntry` interface mirroring the backend model, and `getSessionHistory(taskId)` that returns the rows. 404 from the API is treated as empty array (graceful for tasks with no opencode session yet):

```ts
export interface SessionHistoryEntry {
  id: string;
  session_id: string;
  step: string;
  created_at: string;
  length: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
}

export async function getSessionHistory(taskId: string): Promise<SessionHistoryEntry[]> {
  const response = await fetch(`${API_URL}/api/v1/sessions/${taskId}/history`, {
    credentials: 'include',
  });
  if (response.status === 404) return [];
  if (!response.ok) throw new Error('Failed to fetch session history');
  return response.json();
}
```

---

## Step 4 — New `SessionHistory` component

**File:** `react/src/components/SessionHistory.tsx` (new, 112 lines)

Mirrors the build-plan modal pattern (`SessionArtifacts.tsx:111-134`):

- **Props:** `entries`, `isOpen`, `onClose`, `isLoading`, `error`
- **States:** closed → nothing rendered; loading → spinner; error → error message; empty → "No history yet"; data → timeline of cards
- **Card layout:** step name (monospaced, uppercase, accent color) + relative time header, then a `dl` grid of token fields (input/output/reasoning/cache read/cache write/total). The token block is hidden when all fields are null (old rows from before the token-migration).
- **`formatRelativeTime`:** hand-rolled helper: "Xs ago" / "Xm ago" / "Xh ago" / date string
- **Close:** button + overlay click
- **Memorized:** wrapped in `memo`

Card layout:

```tsx
<li className="session-history-card" data-step={entry.step}>
  <div className="session-history-card-header">
    <span className="session-history-step">{entry.step}</span>
    <time className="session-history-time" dateTime={entry.created_at}>
      {formatRelativeTime(entry.created_at)}
    </time>
  </div>
  {hasTokens && (
    <dl className="session-history-tokens">
      <div><dt>Input</dt><dd>{entry.input_tokens}</dd></div>
      <div><dt>Output</dt><dd>{entry.output_tokens}</dd></div>
      <div><dt>Reasoning</dt><dd>{entry.reasoning_tokens}</dd></div>
      <div><dt>Cache read</dt><dd>{entry.cache_read_tokens}</dd></div>
      <div><dt>Cache write</dt><dd>{entry.cache_write_tokens}</dd></div>
      <div><dt>Total</dt><dd>{entry.length}</dd></div>
    </dl>
  )}
</li>
```

---

## Step 5 — Wire into `SessionArtifacts`

**File:** `react/src/components/SessionArtifacts.tsx`

- Added `historyOpen`, `historyLoading`, `historyError`, `historyEntries` state
- Added `openHistory` async handler that sets open → loading → fetch → populate/error
- Added `hasHistory = !!session.session_id` guard
- Early-return guard updated to include `hasHistory` (so the link renders even when there are no other artifacts)
- New link: `<a class="session-artifacts-link">` with clock SVG icon, rendered when `hasHistory`
- Renders `<SessionHistory>` component alongside build-plan modal block

The same `taskId` already passed in is used — no new props on `SessionArtifacts`, and no changes required in `App.tsx` (the component is already mounted at `App.tsx:131`).

---

## Step 6 — CSS

**File:** `react/src/App.css`

Added ~70 lines of new classes using only existing warp theme CSS variables, reusing the shared `.modal-overlay` / `.modal-content` / `.modal-header` / `.modal-body` / `.modal-footer` classes from the build-plan modal:

| Class | Purpose |
| ----- | ------- |
| `.session-history-modal` | Max-width 720px |
| `.session-history-timeline` | Vertical flex column, 0.75rem gap |
| `.session-history-card` | Bordered card with surface-2 background |
| `.session-history-card-header` | Flex space-between row |
| `.session-history-step` | Monospaced uppercase step name |
| `.session-history-time` | Small tertiary time label |
| `.session-history-tokens` | 3-column grid for token key/value pairs |
| `.session-history-empty/error` | Centered placeholder text |

```css
.session-history-modal { max-width: 720px; }

.session-history-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.session-history-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0.75rem 1rem;
  background: var(--color-surface-2);
}

.session-history-card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5rem;
}

.session-history-step {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-accent);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.session-history-time {
  font-size: 0.7rem;
  color: var(--color-text-tertiary);
}

.session-history-tokens {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem 1rem;
  margin: 0;
  font-size: 0.72rem;
}
.session-history-tokens dt { color: var(--color-text-tertiary); }
.session-history-tokens dd { margin: 0; color: var(--color-text-secondary); font-family: var(--font-mono); }

.session-history-empty,
.session-history-error {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--color-text-tertiary);
  font-size: 0.85rem;
}
```

No new CSS variables — only existing tokens from the warp theme.

---

## Step 7 — Tests

### Backend: API (`tests/test_api.py`)

`TestSessionHistoryEndpoint` with:
- `test_returns_401_without_auth_token` — no cookie → 401
- `test_returns_401_with_invalid_token` — invalid token → 401
- `test_returns_404_when_session_id_not_found` — `get_session_id_by_task_id` returns None → 404
- `test_returns_history_rows` — two rows returned, validates structure and field values

### Backend: Database (`tests/test_database.py`)

`TestGetSessionIdByTaskId` with:
- `test_returns_session_id_for_known_task` — created session → returns session_id
- `test_returns_none_for_unknown_task` — nonexistent task → None
- `test_returns_none_when_session_id_is_empty` — `upsert_pending_session` with `session_id=None` → None

### Frontend: `SessionHistory.test.tsx` (new, 141 lines)

7 cases:
1. Renders nothing when `isOpen=false`
2. Renders loading spinner when `isLoading=true`
3. Renders empty state when `entries=[]`
4. Renders one card per entry with step name
5. Renders token dl only when at least one token field is non-null
6. Calls `onClose` on close-button click
7. Calls `onClose` on overlay click

### Frontend: `SessionArtifacts.test.tsx` (extended)

4 new cases:
1. Renders "View History" link when session has `session_id`
2. Opens history modal on link click → expects "Session History" title + step name
3. Does not render link when `session_id` is empty
4. Renders link for session with only `session_id` and no other artifacts

---

## Test Results

All tests pass:

```
$ uv run ruff check .
All checks passed!

$ uv run ty check
All checks passed!

$ uv run pytest tests/ -q
480 passed in 12.3s

$ cd react && bun run lint
All checks passed!

$ cd react && bun run test
33 passed
```

---

## Open questions

- Should the timeline be infinite-scroll / paginated, or just render all rows? With one row per workflow step (≤ ~10 typical) it doesn't matter today, but a runaway loop or future LLM-call-level granularity could change that.
- Should the relative time switch to absolute on hover (`title={created_at}`)? Cheap to add — recommend yes.

---

## Follow-ups

- Add Escape key handler to the history modal (the build-plan modal already has it via `SessionArtifacts.tsx`)
- Add a `title={entry.created_at}` attribute to `<time>` for hover-to-absolute.
- Verify `record_session_history` coverage — query `SELECT DISTINCT step FROM session_history` after one full end-to-end run to identify uncovered workflow steps.

## References

- [[2026-07-22-react-frontend-template-warp]] — warp theme with the CSS variables used
- [[2026-07-16-session-history-tokens-null]] — why token fields can be null
- `demetra/services/database.py:535` — `get_session_history` (already exists)
- `demetra/library/tables.py:97` — `session_history` table (already exists)
- `react/src/components/SessionArtifacts.tsx:111-134` — build-plan modal to mirror
