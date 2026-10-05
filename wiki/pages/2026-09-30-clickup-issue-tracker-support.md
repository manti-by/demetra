---
title: Switchable issue tracker (Linear / ClickUp)
date: 2026-09-30
type: implementation
status: resolved
session_id: 0b089937-70cf-47c7-bb45-30a65ced6ee1
services: [clickup, linear, tracker, workflows, daemons, agents, settings, library]
branch: clickup-tracker-support
tickets: []
tags: [clickup, linear, tracker, environment, harness, mcp]
related:
  - 2026-09-30-mnt-230-claude-code-harness
  - 2026-09-16-mnt-205-revise-merged-environment
  - 2026-09-11-mnt-203-create-related-ticket-for-research
  - 2026-08-28-mnt-191-ticket-status-not-changed
  - 2026-08-19-split-auth-linear-services-and-review-failure-handling
  - 2026-09-30-move-settings-default-hermetic-tests
---

# Switchable issue tracker (Linear / ClickUp)

## TL;DR

Added ClickUp as a second issue tracker next to Linear, selected the same way the agent harness is: a new
`ISSUE_TRACKER` setting (`linear` | `clickup`, default `linear`) resolved through `SessionEnvironment.issue_tracker`
(project env → user-shared env → settings). A new `demetra/services/tracker/` facade mirrors
`services/agents/harness.py`: workflows, `main.py` and both daemons import only the facade, which dispatches to the
existing `services/linear/` or the new `services/clickup/` (REST v2) backend. No schema change: a ClickUp List plays the
role of the Linear project (`projects.linear_project_id` holds the list id) and the task model stays `LinearTask`.
Claude runs attach only the active tracker's hosted MCP server and tool set. Full suite, ruff, ty and pre-commit green.

---

## Overview

The Linear service was called directly from nine places (`main.py`, `watcher.py`, `services/daemons/watcher.py`,
`workflows/{setup,plan,research,failure,cleanup,merge,rebase,review_fixes}.py`) and workflows resolved ticket states via
`context.environment.linear_state(...)`. The change follows the [[2026-09-30-mnt-230-claude-code-harness]] pattern
exactly: one env key selects the backend, one facade dispatches, both backends keep their own names.

Layering:

- `demetra/library/`: `ISSUE_TRACKERS` + `CLAUDE_CLICKUP_{READ,CREATE}_TOOLS` constants, `ClickUpConfig`/`ClickUpStates`
  TypedDicts, and a new exception base `TrackerError` / `TrackerConfigError` that `LinearError`/`LinearConfigError` and
  the new `ClickUpError`/`ClickUpConfigError` subclass. Workflows now catch only the `Tracker*` bases.
- `demetra/settings.py`: `ISSUE_TRACKER` (validated like `AGENT_HARNESS`) and the `CLICKUP` config block.
- `demetra/services/settings.py`: `settings_default` (moved out of `demetra/library/models.py`) knows `ISSUE_TRACKER`,
  `CLICKUP_TEAM_ID`, `CLICKUP_LIST_ID`, `CLICKUP_DEFAULT_STATE`, `CLICKUP_STATE_*`.
- `demetra/library/models.py`: `SessionEnvironment` gains `issue_tracker`, `clickup_state`,
  `clickup_value` and the dispatching `tracker_state` / `tracker_value`.
- `demetra/services/clickup/`: `api.py` (`clickup_request`, token sent verbatim in `Authorization`), `tasks.py`
  (filtered team tasks polling, per-task comments + threaded replies, `build_task` → `LinearTask`), `mutations.py`
  (status `PUT`, comment `POST`, ticket + idempotent research ticket, cleanup).
- `demetra/services/tracker/__init__.py`: the facade (`get_todo_issues`, `get_task_by_id`, `get_task`,
  `update_ticket_status`, `post_comment`, `create_ticket`, `create_research_ticket`, `tracker_cleanup`,
  `research_labels`, `load_environment`).
- `demetra/services/persistence/database.py`: `get_linked_projects` moved here from `services/linear/tasks.py` so both
  backends share the `projects.linear_project_id` / name → `(project_id, user_id)` lookup.

## Step 1 — Environment resolver

**File:** `demetra/library/models.py`

```python
@property
def issue_tracker(self) -> str:
    value = self.get("ISSUE_TRACKER")
    if value not in ISSUE_TRACKERS:
        raise EnvironmentConfigError(...)
    return value

def tracker_state(self, name: str) -> str:
    if self.issue_tracker == "clickup":
        return self.clickup_state(name)
    return self.linear_state(name)
```

Every workflow call site switched from `linear_state(...)` to `tracker_state(...)` and passes
`environment=context.environment` into the facade's `update_ticket_status` / `post_comment`.

## Step 2 — ClickUp mapping decisions

- **Statuses are labels, not ids.** `CLICKUP_STATE_<NAME>` values (`prd`, `to do`, `in progress`, `in review`,
  `awaiting input`, `complete`) go verbatim into `PUT /task/{id} {"status": ...}`; success is confirmed by comparing the
  returned `status.status` case-insensitively, since ClickUp returns 200 with the unchanged task when the label does not
  exist on the list.
- **List = project.** `LinearTask.linear_project_id` carries the ClickUp list id; `get_linked_projects` matches it (or
  the list name) against `projects.linear_project_id` / `projects.name`. The React project form label now reads
  "Tracker project / ClickUp list ID".
- **Identifier** is `custom_id` when the workspace has custom task ids enabled, else the raw task id (so branch slugs
  still work). **Priority** shares Linear's 1–4 scale via `priority.id`; `null` → 0. **Created at** converts the ms
  epoch to ISO.
- **Comments** need two extra calls per task (`/task/{id}/comment`, then `/comment/{id}/reply` when `reply_count > 0`);
  results are reversed to oldest-first so `LinearTask.text` reads like the Linear renderer.
- **Research ticket** is created in the source task's list in the `prd` status with `markdown_content`; idempotency pages
  the list (`include_closed=true`) and matches the deterministic name client-side because the v2 API has no exact-name
  filter. No team id is required for ClickUp, so `_validate_research_ticket_prerequisites` checks `team_id` only under
  Linear.
- **Create-task body field is `markdown_content`**, not `markdown_description` (that is the *response* field name).

## Step 3 — Daemons

**File:** `demetra/services/daemons/watcher.py`

`resolve_linear_state(name, user_id, project_id)` became `resolve_tracker_environment(user_id, project_id)` (async,
loads both env layers via `tracker.load_environment`) plus a sync `resolve_tracker_state(environment, name)`, so the
same environment is reused for the status move and the comment. `demetra/watcher.py` polls the facade with no
environment, i.e. the tracker `settings.ISSUE_TRACKER` names — see Follow-ups.

## Step 4 — Claude harness

**File:** `demetra/services/agents/claude.py`

`load_claude_agent_definition(agent, tracker)` and `build_claude_mcp_config(project_id, tracker)` pick the tracker's
MCP server (`https://mcp.linear.app/mcp` or `https://mcp.clickup.com/mcp`) and exact tool list; `run_claude_agent`
receives `tracker=_claude_tracker(environment)` from every `claude_*_agent` wrapper. Prompts and both agent-definition
sets (`.claude/agents`, `.opencode/agents`) were reworded to "issue tracker ticket". `opencode.json` ships a disabled
`ClickUp` remote MCP entry.

## Test Results

- `tests/test_clickup.py` (new, 33 tests): request wrapper, parsing, polling/filtering/paging, mutations, research
  ticket idempotency.
- `tests/test_tracker.py` (new): resolution order and per-function dispatch.
- `tests/test_session_environment.py`, `tests/test_settings.py`, `tests/test_claude.py`: tracker resolver, settings
  validation, ClickUp MCP/tool injection.
- Existing watcher/failure/workflow tests updated for the renamed helpers and the `environment=` kwarg.
- `uv run ruff check .`, `uv run ty check`, `uv run pre-commit run --all-files`, full `pytest`, `bun run test`,
  `bun run build`: all green (see the session summary for counts).

---

## Update — 2026-09-30 17:28

- **Verification closed out** — the last red test (`tests/test_venv_bootstrap.py`, it patched the removed
  `setup.get_linear_task` name) now patches `get_task`; two `ty` diagnostics in the new tests (`await_args` is
  `_Call | None`) were fixed by reading `await_args_list[0]`. Final state: full `pytest` 1091 passed, `ruff`, `ty`,
  `pre-commit run --all-files`, `bun run test` (72) and `bun run build` all green.
- **Landed** — committed together with the concurrent LangSmith config work as `013ca41` ("Add ClickUp support, fix
  LangSmith config") on `clickup-tracker-support`. That parallel session also moved `_settings_default` out of
  `demetra/library/models.py` into `demetra/services/settings.py::settings_default` (see
  [[2026-09-30-move-settings-default-hermetic-tests]]); the `ISSUE_TRACKER` / `CLICKUP_*` fallbacks added here now live
  in that module, so the "Step 1" snippet above refers to the resolver methods, not the fallback location.
- **Open question filed** — `wiki/QUESTIONS.md` Q-002 records the single-tracker watcher scope described under
  Follow-ups.

## Follow-ups

- The watcher polls a single tracker (the settings default). A project whose env sets `ISSUE_TRACKER=clickup` while the
  server default is `linear` is only picked up by `main.py --project-name` / `--task-id`, not by the poller. Polling every
  distinct tracker among configured projects is a possible extension; tracked in `wiki/QUESTIONS.md`.
- `CLAUDE_CLICKUP_*` tool names are unverified against a live ClickUp MCP session, same caveat as the Linear set.
- `projects.linear_project_id` / `sessions.linear_link` / `LinearTask` keep their Linear-flavoured names to avoid a
  migration and a rename across React; a rename to `tracker_project_id` is cosmetic and can follow.

## References

- Related: [[2026-09-30-mnt-230-claude-code-harness]], [[2026-09-16-mnt-205-revise-merged-environment]],
  [[2026-09-11-mnt-203-create-related-ticket-for-research]], [[2026-08-28-mnt-191-ticket-status-not-changed]],
  [[2026-08-19-split-auth-linear-services-and-review-failure-handling]],
  [[2026-09-30-move-settings-default-hermetic-tests]]
- External: https://developer.clickup.com/reference/getfilteredteamtasks, https://developer.clickup.com/reference/updatetask,
  https://developer.clickup.com/reference/createtask, https://developer.clickup.com/reference/gettaskcomments
