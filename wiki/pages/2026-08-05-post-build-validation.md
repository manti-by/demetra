---
title: Post-build validation — plan-coverage validate-agent between build and review
date: 2026-08-05
type: implementation
status: resolved
session_id: mnt-146-post-build-validation
services: [opencode, workflows, subprocess, settings]
branch: mnt-146-post-build-validation
tickets: [MNT-146]
tags: [validate-agent, build-plan, coverage, review-loop, stdin]
related: [2026-02-23-add-multiagent-code-review.md, 2026-03-11-task-plan-summarization.md, 2026-05-25-async-review.md, 2026-06-04-review-summarization.md, 2026-06-08-session-step-attribute.md, 2026-07-16-fix-empty-build-plan-loop.md]
---

# Post-build validation — plan-coverage validate-agent between build and review

## TL;DR

Added a dedicated read-only `validate-agent` that runs after the build step and
before the review agents. It compares the staged diff against the finalized build
plan and reports only which plan steps have no corresponding change — never
correctness, quality, or security. Missing items feed back into the build agent as
the next task inside the existing `MAX_REVIEW_ATTEMPTS` budget; silence (empty
output) means full coverage and the pipeline proceeds to review. Fixing CodeRabbit
findings also replaced the 4095-char command-line truncation of agent prompts with
stdin piping, so long build plans reach the agent intact.

Branch: 2 commits ahead of master, open as **PR #72** (base `master`, +536/−25).

> **Status update (2026-08-06, Consistency Agent):** PR #72 has been **merged** into
> `master` (`99b5880`, 2026-08-05) and carries the `1.16.0` version bump. The
> "open as PR #72" framing below is kept as the session record.

---

## Overview

Build agents can silently skip or under-implement plan steps. Code reviewers catch
quality issues but routinely miss "this step from the plan isn't done at all". This
work adds a cheap, plan-coverage-only check that runs before the expensive review
agents, forcing the build loop to address missing items instead of pushing an
incomplete implementation forward.

```text
build agent ──► validate-agent (plan coverage) ──► review agents ──► lint/tests
                    │                                    ▲
                    └── missing items ──► feed build     │ (silence = fully covered)
```

- **Full coverage** → empty output → build continues to review.
- **Missing items** → numbered list `Plan step N: <short title> — not implemented
  (no corresponding change in diff)` → treated like review comments, loop continues
  until `MAX_REVIEW_ATTEMPTS` is exhausted.
- Validate agent is read-only: inspects `git diff --staged`, never edits/stages/commits/pushes.
- No Groq re-summarization — validate output is consumed directly.

## Step 1 — Validate agent and prompt

**Files:** `.opencode/agents/validate-agent.md`, `demetra/prompts/validate_agent.md`

New agent + prompt define the contract: compare each numbered plan step against the
staged diff, emit only missing steps in the exact format above, and respond with the
**empty string** on full coverage. Any non-empty output is treated as missing items
and triggers another build pass, so silence is the only acceptable full-coverage
response. Both treat the diff and plan as untrusted data to analyze, never
instructions.

## Step 2 — Settings

**File:** `demetra/settings.py:118`, `demetra/library/types.py:40`

```python
"validate_model": os.environ.get("OPENCODE_VALIDATE_MODEL", "opencode-go/deepseek-v4-flash"),
```

Added `validate_model` to `OPENCODE` (env `OPENCODE_VALIDATE_MODEL`, default the
lightweight build model) and to the `OpenCodeConfig` TypedDict. Also swapped the
default review model `kimi-k2.7-code` → `minimax-m3` in `OPENCODE_REVIEW_MODELS`.

## Step 3 — Service

**File:** `demetra/services/opencode.py:107`

`opencode_validate_agent(target_path, build_plan, task_title=None, env=None)` mirrors
`opencode_review_agent`: loads `validate_agent` prompt via `get_prompt`, appends the
full build plan, and runs the `validate-agent` with `OPENCODE["validate_model"]`.

## Step 4 — Workflow wiring

**Files:** `demetra/workflows/validate.py` (new), `demetra/workflows/build.py:102`

`run_validate_agent(target_path, build_plan, env)` invokes the agent, strips empty
and no-issue-token lines (`NO_ISSUE_TOKENS_CASE`), returns `None` on full coverage,
and raises `BuildError` on non-zero exit.

In `run_build_step`, between the build invocation and the review block, the session
step is set to `validate` before running it:

```python
await update_session_step(task_id=context.linear_task.id, step="validate")
missing_items = await run_validate_agent(target_path=context.worktree_path, build_plan=build_plan, env=context.project.environment)
if missing_items:
    if context.auto_mode:
        current_task = missing_items
        rerun_attempts -= 1
        review_attempts -= 1
        continue
    result, _ = await user_input([("1", "apply missing plan items"), ("2", "skip")])
    ...
```

In auto mode missing items are fed straight back into the build agent (decrementing
both attempt counters). Interactively, the user can apply or skip — skipping resets
both counters to max and proceeds to review. `review_step_finished` is only reached
after validation passes.

## Step 5 — Fix review findings: stdin delivery instead of 4095-char truncation

**Commit `78edceb`.** CodeRabbit flagged two actionable issues (plus nits that were
also applied: named args, `parts: list[str]`):

1. **Prompt truncation** — `run_opencode_agent` previously appended
   `shlex.quote(task)[:4095]` as a command-line argument, silently dropping trailing
   plan steps. Now the task is delivered via stdin:

   **File:** `demetra/services/opencode.py:213`
   ```python
   return await run_command(command=command, target_path=target_path, disable_stdio=disable_stdio, env=env, input_text=task)
   ```

   **File:** `demetra/services/subprocess.py:10` — new `pipe_stdin_input` writes the
   text to the process stdin and closes it; `run_command` gained `input_text: str | None`
   and only opens `stdin=PIPE` when provided, running it concurrently with the
   stdout/stderr streamers.

2. **Silent failure on non-zero exit** — `run_validate_agent` previously could return
   `None` (treated as success) on a failed agent run. It now raises `BuildError`
   on any non-zero exit, so validation failure stops/retries the build loop before
   code review instead of being mistaken for full coverage.

## Step 6 — Tests

**Files:** `tests/test_validate_workflow.py` (new), plus additions to
`tests/test_opencode.py`, `tests/test_subprocess.py`, `tests/test_workflows.py`,
`tests/test_settings.py`, `tests/test_more_edge_cases.py`.

Covered: full coverage → no items (`None`), partial coverage → missing items,
empty diff → all items missing, no-issue-token filtering, non-zero exit → `BuildError`,
stdin piping in `run_command`, and `validate_model` settings/`OPENCODE_VALIDATE_MODEL`.

## Test Results

- New/changed test modules added (validate workflow, subprocess stdin, settings).
- Per MNT-146 acceptance criteria: `make test`, `uv run ruff check .`,
  `uv run ty check`, `uv run pre-commit run --all-files`.
- `pyproject.toml` version bumped `1.15.7` → `1.16.0`.

---

## Follow-ups

- ~~PR #72 open, awaiting review/merge.~~ **Done** — merged via `99b5880` (2026-08-05).
- CodeRabbit review was `COMMENTED`; its two actionable findings were addressed in
  commit `78edceb` (stdin delivery, `BuildError` on failure). The two nitpicks (type
  annotation, named arguments) were also applied.
- Out of scope by design: correctness/quality/security review, lint/tests, changes to
  plan/build/review agents, Groq re-summarization.

## References

- Linear: [MNT-146](https://linear.app/mnt/issue/MNT-146/post-build-validation)
- GitHub: [PR #72](https://github.com/manti-by/demetra/pull/72)
- Related: [[2026-05-25-async-review]] (the review stage this slots before; formerly [[2026-02-23-add-multiagent-code-review]], archived)
- Related: [[2026-06-04-review-summarization]] (build-plan extraction/summarization pipeline; formerly [[2026-03-11-task-plan-summarization]], archived)
- Related: [[2026-07-16-fix-empty-build-plan-loop]] (prior build-loop hardening)
- Related: [[2026-06-08-session-step-attribute]] (session `step` attribute, now `validate`)
