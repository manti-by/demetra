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
related: [2026-07-16-fix-empty-build-plan-loop.md, 2026-08-05-post-build-validation.md, 2026-08-28-mnt-177-workflow-blocked-openrouter-403.md]
---

# Guard empty plan agent output

## TL;DR

Every workflow run was showing "No implementation plan was provided in the plan output" as the build plan. That sentence is not a Demetra error — it is what the `extract_plan` summarizer LLM returns when the plan agent's stdout is empty. The plan agent (`opencode run --agent plan-agent`, `minimax-m3`) exits 0 with empty output when its run ends on a permission auto-rejection, and `run_plan_step` fed that empty string straight into the summarizer, which fabricated the sentence and let it through as a real plan. Fixed by guarding `run_plan_step`: empty/whitespace output and output missing the `## Implementation Plan` header now raise `PlanError`, post an `## Error` comment to the ticket, and move it to Awaiting Input instead of continuing with a hallucinated plan.

---

## Overview

**Symptom:** workflow runs showed `No implementation plan was provided in the plan output` as the "Plan output" and continued into the build step with that garbage as the plan (session log `7bfff9b1`, MNT-166).

**Root cause chain:**

1. The plan agent ended its run immediately after a permission auto-rejection (`! permission requested: read (.env.docker.example); auto-rejecting` → `Error: The user rejected permission to use this specific tool call.`) and exited **0 with empty stdout**.
2. `run_plan_step` (`demetra/workflows/plan.py`) passed that empty `plan_output` straight into `extract_plan` (`demetra/services/llm/openrouter.py`), which runs the `summarize_plan` prompt over OpenRouter.
3. The LLM, given empty input, responded with the sentence "No implementation plan was provided in the plan agent output." — and because the string was non-empty, the `if not build_plan:` guard never fired. The sentence was saved as `build_plan` and handed to the build agent.

The same pattern is visible in older session logs (`58354057`, `5ee5407b`, `4bf5abe8`, `a812cfbf`, `80243eb8`): a permission rejection near the end of the plan run produces empty output and a fabricated plan.

## Step 1 — Guard empty plan agent output

**File:** `demetra/workflows/plan.py:83-100`

Strip the stdout once, then reject empty output before summarization:

```python
plan_output = stdout.strip()
print_message(f"Plain plan agent output:\n{plan_output}", style="info")

try:
    if not plan_output:
        raise PlanError("Plan agent produced no output")
    if PLAN_HEADER_STRING not in plan_output:
        raise PlanError("Plan agent output is missing the implementation plan section")
    build_plan = await extract_plan(
        plan_output=plan_output,
        task_description=context.linear_task.description,
        comments=context.linear_task.comments,
        user_id=context.project.user_id,
    )
except PlanError as e:
    print_message(f"Plan step failed: {e}", style="error")
    await post_comment(task_id=context.linear_task.id, body=f"## Error\nPlan step failed: {e}")
    await move_to_awaiting_input(context=context)
```

The guards reuse the existing `except PlanError` handler, so a bad run posts a clear `## Error` comment on the Linear ticket and moves it to Awaiting Input (via `AutoCancelledError`) instead of silently continuing.

## Step 2 — Guard missing plan header

The `## Implementation Plan` header is the plan agent's mandated output contract (`.opencode/agents/plan-agent.md`). Requiring it in the raw output catches the wider class of the bug — output that is non-empty but contains no plan section — which the summarizer could otherwise fabricate a "plan" from. `PLAN_HEADER_STRING` is imported from `demetra.services.agents.opencode` (existing constant).

## Test Results

- 2 new tests in `tests/test_workflows.py`: `test_run_plan_step_empty_agent_output_moves_to_awaiting_input` and `test_run_plan_step_output_missing_plan_header_moves_to_awaiting_input` — both assert `AutoCancelledError`, one `post_comment` call, ticket moved to `awaiting-input-state-id`, and that `extract_plan` was never called.
- Updated 2 existing plan tests whose mock plan output lacked the header (`test_run_plan_step_returns_build_plan`, `test_run_plan_step_empty_plan_returns_none`).
- `uv run pytest tests/test_workflows.py -q` — **42 passed**.
- `uv run ruff check demetra/workflows/plan.py tests/test_workflows.py` — clean.
- `uv run ty check demetra/workflows/plan.py tests/test_workflows.py` — clean.

---

## Follow-ups

- The underlying opencode behavior (permission auto-rejection ending a plan run with exit 0 and empty stdout) is not fixed — the guard turns it into a visible, handled failure instead. If it recurs often, consider whether the plan agent should be granted read access to `.env.docker.example`-style files or whether a permission-denied tool call should abort the run with a non-zero exit.
- **Recurred 2026-08-28 on MNT-177:** the same `read (.env.docker.example); auto-rejecting` truncation cut off two plan-agent runs (`Plan agent output is missing the implementation plan section`), and a second, unrelated blocker dominated — the user-shared `OPENROUTER_MODEL=meta/muse-spark-1.2` returned OpenRouter 403 (18+ age attestation) in 3 of 6 runs. See [[2026-08-28-mnt-177-workflow-blocked-openrouter-403]].

## References

- Related: [[2026-07-16-fix-empty-build-plan-loop]], [[2026-08-05-post-build-validation]]
- External: session log `7bfff9b1-8696-43ef-be47-46e5dac0e81f.log` (MNT-166), `demetra/workflows/plan.py`, `demetra/services/llm/openrouter.py`
