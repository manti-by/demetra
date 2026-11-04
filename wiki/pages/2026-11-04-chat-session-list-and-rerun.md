---
title: Chat session list and rerun semantics
date: '2026-11-04'
type: implementation
status: resolved
session_id: ses_e5d431134ffe82sdvcgjvtkTgc
services: [react, api, persistence, vcs, workflows]
branch: opencode/feature/chat-session-list-and-rerun
tickets: []
tags: [frontend, sessions, feedback-loops, chat, rerun]
related: [2026-10-12-session-state-flow-feedback-loops.md, 2026-11-03-ch-2-single-unified-session-view.md, 2026-09-24-mnt-219-session-log-autoscroll.md]
---

# Chat session list and rerun semantics

## TL;DR
The sidebar item now reads as three rows — type/status/time, title, project chip and labels — with `project_name` joined into the sessions and chats APIs. Feedback-loop arrows are no longer ephemeral client state: review→build and lint/test→build attempts are counted from `session_history`, returned by the API and websocket, and restored after a reload (blinking while the workflow runs, bright and still once it finishes). Chat descriptions became read-only, and Re-run now resumes the stored plan/session instead of resetting the run; failed chat runs keep their worktree and branch so the resume has files to continue.

## Overview
Four related changes to the chat/session surface: the session list redesign, persisted feedback-loop counters, chat project names, and the Re-run/description policy. The common thread is moving state that lived only in the browser (loop arrows, description edits, step resets) into stored session history or explicit API actions.

## Step 1 — Three-row session item with type badge and project
**File:** `react/src/components/SessionList.tsx`

The item lost the inline build-plan text and the colored status dot. It renders:

- row 1 — a single-letter type badge (`C` chat / `L` linear, tooltip names the type), the step badge, and the relative time pushed right;
- row 2 — the session title;
- row 3 — the project chip followed by the chat tags.

**File:** `demetra/services/persistence/database.py` — `get_sessions` outer-joins `projects` and selects `projects.name AS project_name`; rows without a live project (legacy sessions) simply omit the chip.

**File:** `react/src/services/api.ts` — `Session` gained `project_id`, `project_name` and later `feedback_loops`; `App.css` adds `.session-type`, `.session-item-badges` and `.session-project` (accent left border on `--color-surface-3`) and the style guide mirrors the new layout.

## Step 2 — Feedback loops counted from session history
**File:** `demetra/services/persistence/database.py`

`get_feedback_loops(task_ids=[...])` is one window query over `session_history`: `lag(step)` partitioned by task orders `kind IN ('invocation','step')` rows restricted to `build/review/lint/test`, then counts `build` rows preceded by `review` (`review`) or by `lint`/`test` (`test`). Repeated review invocations and build retries in one round collapse to a single transition; `llm_call` rows are excluded because their `step` is a prompt name.

`record_session_step` gained `repeat=True`, used by the lint and test steps (`demetra/workflows/lint.py`), so every attempt appends its own history row — the default upsert kept only the first occurrence and made test-loop counts impossible.

The counts surface in every path the UI consumes:

- `get_sessions` → `feedback_loops` on each row;
- `SessionState.feedback_loops` → chat detail (`GET /api/v1/chats/{id}`);
- `send_status` in `demetra/api/watcher.py` → the 1s websocket status envelope, so counts update without waiting for the 60s session-list poll.

**File:** `react/src/components/SessionStateFlow.tsx`

`SessionStateFlow` accepts `feedbackLoops`; a bracket is taken when the live `review → build`/`lint+test → build` transition was observed or the persisted count is non-zero. `resolveLoopState(taken, finished)` renders:

- `pending` — dashed, no label (loop never taken);
- `active` — blinking (workflow still running);
- `passed` — `--color-warning` without animation (`completed`/`failed`/`awaiting_input`); the bracket stops blinking while the workflow waits for input.

The live `previousStepRef` detection stays for instant feedback between polls.

## Step 3 — Chat project name in the API
**File:** `demetra/services/persistence/database.py`

`_chat_select()` is `SELECT chats.*, projects.name AS project_name FROM chats JOIN projects ON projects.id = chats.project_id`, used by `get_chat_by_task_id`, `get_chat` and `list_chats`. `create_chat` looks the name up after the chat insert (so an unknown project still raises the existing `IntegrityError`) and includes it in the returned `Chat`; the `Chat` dataclass and the React `Chat` interface carry `project_name`.

## Step 4 — Read-only description and resuming Re-run
**Description.** Removed `PATCH /api/v1/chats/{task_id}`, the `UpdateChat` model, `update_chat`, `update_session_step_if_stopped` and the FE `updateChat` client. `ChatPanel` renders `chat.description` as pre-wrapped text (`.chat-description-text`); it is set only at creation now.

**Re-run.** New `POST /api/v1/chats/{task_id}/rerun` (FE `rerunChat`); the endpoint checks the project is still ready via `is_project_ready` before claiming. `claim_session_for_rerun` is an atomic conditional update from `failed`/`awaiting_input`: a posted plan with content keeps `build_plan`, `posted_to_linear`, `run_attempts` and `session_id` and resumes at `step='build'`; a plan without approval (never posted, or a posted flag without plan content — the plan agent stopped with open questions before the plan reached the thread) instead clears the plan, resets the posted flag and restarts at `initial` with an `initial` step row in the timeline, so the rerun cannot build without the requested answers. With the plan kept, `main.py` skips `run_plan_step` and goes straight to build (the first build invocation forks the previous opencode session once). The step change also makes the claim exclusive, and the Re-run button is now limited to `failed`/`awaiting_input`.

**Failed-run workspace.** `git_cleanup` returns early for chat failures, keeping the worktree and branch; `git_worktree_create` gained `reuse_existing`, and `setup_workflow` passes it for chat tasks, so a rerun continues the files (including uncommitted build changes) instead of recreating the worktree from the branch. Completed runs still remove the worktree and keep the branch.

## Test Results
- Python: 1190 passed; `ruff`, `ty`, `bandit` and pre-commit clean.
- React: 144 passed; `tsc` + Vite build clean.
- New coverage: feedback-loop counting (including repeated lint/test rows), `claim_session_for_rerun` state preservation/exclusivity, rerun API (state, 409s, user scoping, enqueue failure), chat-failure cleanup retention, worktree reuse, and the read-only description/Re-run visibility in `ChatPanel`.

## Follow-ups
- Deleting a chat session does not remove a worktree preserved by a failed run; it lingers until the same branch is rerun or cleaned manually.
- `run_attempts` is deliberately not reset, so a chat that exhausted `MAX_ATTEMPTS["run"]` cannot be rerun (hard stop).

## References
- Related: [[2026-10-12-session-state-flow-feedback-loops]]
- Related: [[2026-11-03-ch-2-single-unified-session-view]]
- Related: [[2026-09-24-mnt-219-session-log-autoscroll]]
