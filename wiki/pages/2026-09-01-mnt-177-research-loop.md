---
title: MNT-177 research loop — research agent, workflow and settings
date: 2026-09-01
type: implementation
status: resolved
session_id: ses_mnt177_20260901
services:
- workflows
- agents
- opencode
- linear
- settings
- prompts
branch: mnt-177-research-loop
tickets:
- MNT-177
tags:
- research
- research-agent
- research-report
- research-labels
- opencode
- workflow
- awaiting-input
related:
- 2026-08-28-mnt-177-workflow-blocked-openrouter-403.md
- 2026-08-24-guard-empty-plan-output.md
- 2026-08-18-migrate-llm-groq-to-openrouter.md
- 2026-09-02-review-findings-cleanup.md
- 2026-09-14-opencode-agent-prompts-hardening.md
- 2026-09-10-mnt-200-update-research-loop.md
---
# MNT-177 research loop — research agent, workflow and settings

## TL;DR

Added Research loop: tickets with `Research` label run a read-only `research-agent` (wiki + web validation) that extracts `## Research Report`, posts it as a Linear comment, and moves the ticket to `Awaiting Input`. Branch short-circuits the normal plan→build pipeline in `main.py`. Added `MAX_RESEARCH_ATTEMPTS=5`, `OPENCODE["research_model"]`, `LINEAR["research_labels"]`, `research` StepType. 920 tests, ruff/ty/bandit green.

---

## Overview

**Ticket:** [MNT-177](https://linear.app/mnt/issue/MNT-177/research-loop) — run research agent instead of plan agent when Research label present. Prior workflow (`main.py` → `run_plan_step` → `run_build_step` → `commit_and_push` → `cleanup_workflow`) had no label branching or `research` step. Follows plan comment's 10 steps.

## Changes

**Step 1 — `demetra/library/models.py:9`:** added `"research"` to `StepType` Literal.

**Step 2 — `demetra/library/types.py:17`:** `LinearConfig.research_labels: list[str]`, `OpenCodeConfig.research_model: str`.

**Step 3 — `demetra/settings.py:43` / `.env.docker.example:59`:** `MAX_RESEARCH_ATTEMPTS = env_get_int("MAX_RESEARCH_ATTEMPTS", 5)`, `LINEAR["research_labels"] = env_get_list("LINEAR_RESEARCH_LABELS", ["Research"])` (case-insensitive check), `OPENCODE["research_model"] = env_get_str("OPENCODE_RESEARCH_MODEL", "opencode-go/minimax-m3")` via `_resolve_opencode_model`; added commented `# MAX_RESEARCH_ATTEMPTS=5`.

**Step 4 — `.opencode/agents/research-agent.md`:** read-only prompt mirroring `plan-agent.md`; wiki first, then web, codebase scan only if strictly necessary; mandates `## Research Report` with summary/validation/risks/next steps.

**Step 5 — `demetra/prompts/research_agent.md`:** template with `{task}` via `get_prompt(name="research_agent", task=task)`, instructs wiki + web synthesis with citations.

**Step 6 — `demetra/services/agents/opencode.py:14`:** added `RESEARCH_HEADER_STRING = "## Research Report"`, `opencode_research_agent(target_path, task, task_title, env, user_environment)` (resolves `OPENCODE_RESEARCH_MODEL` via `_resolve_opencode_model`, `agent="research-agent"`), `extract_research_report(str) -> str` (slice from header, no terminal markers).

**Step 7 — `demetra/workflows/research.py`:** `is_research_ticket(context)` — case-insensitive intersection of `LINEAR["research_labels"]` vs `context.linear_task.labels`; `run_research_step(context) -> str | None` loops `MAX_RESEARCH_ATTEMPTS`: `update_session_step(step="research")` → `opencode_research_agent` → check `exit_code` + `RESEARCH_HEADER_STRING` → `extract_research_report` → `post_comment` → move to `awaiting_input` + `update_session_step(step="awaiting_input")`. Empty/missing-header or non-zero exit retries; `LinearError` on mutation prevents reaching `Awaiting Input` without posted report.

**Step 8 — `main.py:31`:** after moving to `in_progress`, branch:

```python
if is_research_ticket(context=context):
    report = await run_research_step(context=context)
    if report is None:
        return
    is_success = True
    should_update_linear_status = False
    return
```

`None` keeps `is_success=False` → normal failure cleanup; `should_update_linear_status=False` preserves `awaiting_input` (otherwise `cleanup_workflow` would move to `done`). `finally` still removes worktree.

## Deviations

- **Frontend:** plan listed BE files only — React untouched; research settings env-only.
- **Tests:** `TestOpencodeResearchAgent` / `TestWorkflowResearch` landed next day in [[2026-09-02-review-findings-cleanup]].

## Test Results

- `uv run ruff check .` / `uv run ty check` / `uv run bandit -c pyproject.toml -r demetra` (10139 lines) — clean
- `uv run pytest tests/test_opencode.py tests/test_workflows.py -q` — 79 passed; `tests/ -q` — 920 passed

## Follow-ups

- Decide if React should surface research settings or env-only suffices.
- Consider reusing `research` step in session history aggregation.

> **2026-09-14:** `research-agent.md` was only agent with `description`/`permission` until [[2026-09-14-opencode-agent-prompts-hardening]] brought other six to same standard.
> **Consistency note (2026-09-02):** `opencode_research_agent` gained `project_id` param and label check split into `is_research_task(linear_task)` / `is_research_ticket(context)` (`demetra/workflows/research.py`).

> **Consistency note (2026-09-15, Consistency Agent):** Post-research step `awaiting_input` superseded by [[2026-09-10-mnt-200-update-research-loop]] — now `researched` (`sessions.research_report` persisted, navy badge). Earlier `awaiting_input` wording above is stale, verified against `demetra/library/models.py:26` `StepType` and `demetra/workflows/research.py`.

## References

- Related: [[2026-08-28-mnt-177-workflow-blocked-openrouter-403]], [[2026-08-24-guard-empty-plan-output]], [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-09-02-review-findings-cleanup]], [[2026-09-14-opencode-agent-prompts-hardening]]
- External: [MNT-177 — Research loop](https://linear.app/mnt/issue/MNT-177/research-loop)

> **Consistency fix (2026-09-02):** added `2026-09-02-review-findings-cleanup.md` to `related`.
