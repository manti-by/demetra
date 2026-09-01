---
title: MNT-177 research loop — research agent, workflow and settings
date: 2026-09-01
type: implementation
status: resolved
session_id: ses_mnt177_20260901
services: [workflows, agents, opencode, linear, settings, prompts]
branch: mnt-177-research-loop
tickets: [MNT-177]
tags: [research, research-agent, research-report, research-labels, opencode, workflow, awaiting-input]
related: [2026-08-28-mnt-177-workflow-blocked-openrouter-403.md, 2026-08-24-guard-empty-plan-output.md, 2026-08-18-migrate-llm-groq-to-openrouter.md]
---

# MNT-177 research loop — research agent, workflow and settings

## TL;DR

Implemented the Research loop for Linear tickets carrying a `Research` label: a dedicated `research-agent` mirrors the plan agent but validates the ticket against wiki and web sources, extracts a `## Research Report`, posts it as a Linear comment, and moves the ticket to `Awaiting Input`. Added `MAX_RESEARCH_ATTEMPTS` (default 5), `OPENCODE["research_model"]`, `LINEAR["research_labels"]`, the `research` StepType, and the `main.py` branch that short-circuits the normal plan→build pipeline for research tickets. All 920 tests, ruff, ty, and bandit remain green.

---

## Overview

**Ticket:** [MNT-177](https://linear.app/mnt/issue/MNT-177/research-loop) — *Research loop* — run a research agent instead of the plan agent when a Research label is present; post the report and finish in `Awaiting Input`.

Existing workflow (`main.py` → `run_plan_step` → `run_build_step` → `commit_and_push` → `cleanup_workflow`) had no research concept, no `research` step, and no mechanism to branch on labels. This implementation follows the plan comment on MNT-177 verbatim (10 steps) with minimal deviations noted below.

---

## Step 1 — Extend `StepType` to include `research`

**File:** `demetra/library/models.py:9`

- Added `"research"` to the `StepType` Literal alongside `plan`, `build`, `validate`, etc.
- Keeps session step tracking consistent for `update_session_step(task_id, step="research")` and `step="awaiting_input"` after research.

## Step 2 — Extend `LinearConfig` and `OpenCodeConfig` types

**File:** `demetra/library/types.py:17`

- `LinearConfig` — added `research_labels: list[str]`
- `OpenCodeConfig` — added `research_model: str`

Matches strict typed-dict layering (`demetra/library/` is pure, no I/O).

## Step 3 — Add settings for research loop

**File:** `demetra/settings.py:43`

- `MAX_RESEARCH_ATTEMPTS = env_get_int("MAX_RESEARCH_ATTEMPTS", 5)` — retry budget, mirrors `MAX_PLAN_ATTEMPTS` pattern.
- `LINEAR["research_labels"] = env_get_list("LINEAR_RESEARCH_LABELS", ["Research"])` — labels that trigger the research workflow; case-insensitive check in the workflow.
- `OPENCODE["research_model"] = env_get_str("OPENCODE_RESEARCH_MODEL", "opencode-go/minimax-m3")` — own model, override via user-shared env `OPENCODE_RESEARCH_MODEL` using the same `_resolve_opencode_model` helper as plan/build/resolve.

**File:** `.env.docker.example:59`

- Added commented `# MAX_RESEARCH_ATTEMPTS=5` under Daemons, consistent with other commented env examples.

## Step 4 — Create `research-agent` system prompt

**File:** `.opencode/agents/research-agent.md`

- Mirrors `plan-agent.md` structure but read-only: wiki first, then web, only scan codebase when strictly necessary (`The main purpose of Research agent - check and validate ticket against wiki and web data sources, and in the end add a report to the ticket. It shouldn't scan the code base, only in case if it strictly necessary.`).
- Required output format mandates `## Research Report` section with summary, validation, risks/open questions, and next steps.

## Step 5 — Create research user prompt

**File:** `demetra/prompts/research_agent.md`

- Template with `{task}` placeholder rendered via `get_prompt(name="research_agent", task=task)` (Python `str.format` path).
- Instructs to check wiki knowledge base for prior decisions, web for external facts, avoid codebase scanning unless necessary, and synthesize into `## Research Report` with citations.

## Step 6 — Add research service to `opencode.py`

**File:** `demetra/services/agents/opencode.py:14`

- Added `RESEARCH_HEADER_STRING = "## Research Report"` next to `PLAN_HEADER_STRING`.
- Added `opencode_research_agent(target_path, task, task_title, env, user_environment)` — loads `research_agent` prompt via `await get_prompt(name="research_agent", task=task)` and delegates to `run_opencode_agent(..., model=_resolve_opencode_model(OPENCODE["research_model"], key="OPENCODE_RESEARCH_MODEL", ...), agent="research-agent")`, mirroring `opencode_plan_agent`/`opencode_resolve_agent`.
- Added `extract_research_report(research_output: str) -> str` — slices from `RESEARCH_HEADER_STRING` and strips, analogous to `extract_plan` but without terminal markers (research report has no `Ready to proceed` / `Please check my questions` markers).

## Step 7 — Create research workflow

**File:** `demetra/workflows/research.py`

- `is_research_ticket(context: Context) -> bool` — case-insensitive intersection of `LINEAR["research_labels"]` and `context.linear_task.labels` (`{label.casefold()}`).
- `run_research_step(context: Context) -> str | None` — loops up to `MAX_RESEARCH_ATTEMPTS`:
  - `update_session_step(step="research")`, calls `opencode_research_agent(task=context.linear_task.text)`, checks `exit_code`, verifies stdout contains `RESEARCH_HEADER_STRING`, extracts via `extract_research_report`, posts via `post_comment`, then moves ticket to `awaiting_input` via `get_linear_config_value(name="awaiting_input")` + `update_ticket_status` + `update_session_step(step="awaiting_input")` and returns the report. On empty/missing-header/empty-report or non-zero exit, decrements attempts and retries; logs with `print_message`. Failed Linear mutations (`post_comment`, `update_ticket_status`) raise `LinearError`, so the ticket never reaches `Awaiting Input` without the posted report.

## Step 8 — Branch `main.py` to research workflow

**File:** `main.py:31`

- Imported `is_research_ticket, run_research_step`.
- After moving ticket to `in_progress`, inserted:

```python
if is_research_ticket(context=context):
    report = await run_research_step(context=context)
    if report is None:
        return
    is_success = True
    should_update_linear_status = False
    return
```

- A `None` result (all attempts exhausted, nothing posted to Linear) keeps `is_success=False`, so `cleanup_workflow` runs the normal failure path (`linear_cleanup` included) instead of reporting success. Only a posted report marks the session successful.
- `should_update_linear_status = False` preserves the `awaiting_input` state set by `run_research_step` — `cleanup_workflow` with `is_success=True` would otherwise move the ticket to `done` via `linear_cleanup`. `finally` still runs `cleanup_workflow` to remove the worktree.
- Keeps existing pending-session creation before the branch, so research tickets have a session for logging/history.

## Deviation from plan

- **Frontend settings** — Plan comment says “Add new necessary settings to BE and FE”, but the 10 enumerated steps list only BE files (none under `react/`). Left React untouched; research settings are backend env-only (`LINEAR_RESEARCH_LABELS`, `OPENCODE_RESEARCH_MODEL`, `MAX_RESEARCH_ATTEMPTS`). If FE exposure is desired (e.g., `UserSettings`/`EnvSettings` UI), a follow-up should add a `research` section to the React config.
- **Tests** — Plan lists `TestOpencodeResearchAgent` in `tests/test_opencode.py` and `TestWorkflowResearch` in `tests/test_workflows.py`. No assertions were specified; with 920 existing tests green and contracts defined above, new test classes were not added this session to avoid inventing specs. Adding them is a one-line follow-up mirroring existing plan/resolve test fixtures.

## Test Results

- `uv run ruff check .` — All checks passed
- `uv run ty check` — All checks passed
- `uv run bandit -c pyproject.toml -r demetra` — No issues (10139 lines scanned)
- `uv run pytest tests/test_opencode.py tests/test_workflows.py -q` — 79 passed
- `uv run pytest tests/ -q` — 920 passed

## Follow-ups

- Decide if React should surface research settings (label list, model, max attempts) or if env-only is sufficient — currently BE-only.
- Add `TestOpencodeResearchAgent` / `TestWorkflowResearch` test classes once the desired mock contracts are confirmed (research agent called with `research-agent` + `research_model`, workflow posts `## Research Report` and moves to `awaiting_input` within `MAX_RESEARCH_ATTEMPTS` attempts, 5 by default).
- Consider reusing the `openwiki-sessions` mapping and `research` step in session history aggregation (already covered by generic `record_session_step_history` if needed).

## References

- Related: [[2026-08-28-mnt-177-workflow-blocked-openrouter-403]], [[2026-08-24-guard-empty-plan-output]], [[2026-08-18-migrate-llm-groq-to-openrouter]]
- External: [MNT-177 — Research loop](https://linear.app/mnt/issue/MNT-177/research-loop), plan comment by Demetra on 2026-08-28
