---
title: Guard empty plan agent output
date: 2026-08-24
type: implementation
status: resolved
session_id: ses_fcc17abbaffe7m4bui291JEEZ3
services: [workflows, opencode, llm]
branch: "-"
tickets: []
tags: [plan-agent, plan-step, empty-output, guard, error-handling, extract-plan]
related:
- 2026-09-14-opencode-agent-prompts-hardening.md
- 2026-08-28-mnt-177-workflow-blocked-openrouter-403.md
- 2026-07-16-fix-empty-build-plan-loop.md
- 2026-08-05-post-build-validation.md
---

# Guard empty plan agent output

## TL;DR

Workflow showed `No implementation plan was provided in the plan output` as the build plan — a hallucination by the `extract_plan` LLM given empty stdout. The plan agent (`opencode run --agent plan-agent`, `minimax-m3`) exits 0 with empty output after a permission auto-rejection. Fixed in `demetra/workflows/plan.py:83-100`: empty/whitespace output or missing `## Implementation Plan` header now raises `PlanError` → posts `## Error` comment and moves ticket to `Awaiting Input` instead of continuing.

## Overview

**Chain:** permission auto-rejection (`! permission requested: read (.env.docker.example); auto-rejecting` → `Error: The user rejected permission...`) ends plan run with exit 0 + empty stdout → `run_plan_step` (`demetra/workflows/plan.py`) fed empty string to `extract_plan` (`demetra/services/llm/openrouter.py`) → LLM fabricated "No implementation plan was provided..." → non-empty string bypassed `if not build_plan:` guard. Same pattern in logs `58354057`, `5ee5407b`, `4bf5abe8`, `a812cfbf`, `80243eb8`. Session `7bfff9b1` (MNT-166) showed garbage plan continuing to build.

## Fix

`demetra/workflows/plan.py:83-100` — strip once, validate before summarization, reuse existing `except PlanError` path:
```python
plan_output = stdout.strip()
if not plan_output:
    raise PlanError("Plan agent produced no output")
if PLAN_HEADER_STRING not in plan_output:
    raise PlanError("Plan agent output is missing the implementation plan section")
build_plan = await extract_plan(...)
except PlanError as e:
    await post_comment(task_id=..., body=f"## Error\nPlan step failed: {e}")
    await move_to_awaiting_input(context=context)
```
`PLAN_HEADER_STRING` (`## Implementation Plan`) from `demetra.services.agents.opencode` is the plan-agent contract (`.opencode/agents/plan-agent.md`).

## Test Results

- 2 new tests `test_run_plan_step_empty_agent_output_moves_to_awaiting_input` / `test_run_plan_step_output_missing_plan_header_moves_to_awaiting_input` — assert `AutoCancelledError`, one `post_comment`, `awaiting-input-state-id`, `extract_plan` never called
- Updated 2 existing plan tests to include header in mock output
- `uv run pytest tests/test_workflows.py -q` — **42 passed**; `ruff check` / `ty check` clean

## Follow-ups

- Auto-rejection with exit 0 not fixed — guard makes it a handled failure. Consider granting read to `.env.docker.example`-style files or failing non-zero on permission denial.
- **2026-09-14:** 6 agents now declare explicit `permission` blocks — see [[2026-09-14-opencode-agent-prompts-hardening]] (machine-enforced scope, not a fix for auto-rejection).
- **2026-08-28 MNT-177 recurred:** same `read (.env.docker.example); auto-rejecting` truncation plus unrelated `OPENROUTER_MODEL=meta/muse-spark-1.2` → OpenRouter 403 (18+ attestation) in 3/6 runs — see [[2026-08-28-mnt-177-workflow-blocked-openrouter-403]].

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-16-fix-empty-build-plan-loop]], [[2026-08-05-post-build-validation]], [[2026-09-14-opencode-agent-prompts-hardening]]
- External: session log `7bfff9b1-8696-43ef-be47-46e5dac0e81f.log` (MNT-166), `demetra/workflows/plan.py`, `demetra/services/llm/openrouter.py`
