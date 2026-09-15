---
title: Post-build validation — plan-coverage validate-agent between build and review
date: 2026-08-05
type: implementation
status: resolved
session_id: mnt-146-post-build-validation
services:
- opencode
- workflows
- subprocess
- settings
branch: mnt-146-post-build-validation
tickets:
- MNT-146
tags:
- validate-agent
- build-plan
- coverage
- review-loop
- stdin
related:
- 2026-02-23-add-multiagent-code-review.md
- 2026-03-11-task-plan-summarization.md
- 2026-08-18-migrate-llm-groq-to-openrouter.md
- 2026-07-16-fix-step-status-review-findings.md
- 2026-07-16-fix-empty-build-plan-loop.md
---
# Post-build validation — plan-coverage validate-agent between build and review

## TL;DR

Added a read-only `validate-agent` between build and review that compares the staged diff against the build plan and reports only uncovered plan steps. Missing items feed back into the build loop within `MAX_REVIEW_ATTEMPTS`; empty output means full coverage. Also fixed the 4095-char CLI truncation by piping task prompts via stdin.

Branch: 2 commits ahead of master, merged as **PR #72** (`99b5880`, 2026-08-05, `1.16.0`).

---

## Overview

Build agents can silently skip plan steps; reviewers catch quality issues but miss uncovered steps. This adds a cheap coverage gate before expensive review.

```text
build agent ──► validate-agent (plan coverage) ──► review agents ──► lint/tests
                    └── missing items ──► feed build (silence = fully covered)
```

- Full coverage → empty output → proceed to review.
- Missing items → `Plan step N: <title> — not implemented (no corresponding change in diff)` → build loop continues until `MAX_REVIEW_ATTEMPTS`.
- Read-only: inspects `git diff --staged`, never edits. No Groq re-summarization.

## Step 1 — Validate agent and prompt

**Files:** `.opencode/agents/validate-agent.md`, `demetra/prompts/validate_agent.md`

Contract: compare each numbered plan step against staged diff, emit only missing steps in exact format above, return **empty string** on full coverage. Diff and plan treated as untrusted data.

## Step 2 — Settings

**File:** `demetra/settings.py:118`, `demetra/library/types.py:40`

```python
"validate_model": os.environ.get("OPENCODE_VALIDATE_MODEL", "opencode-go/deepseek-v4-flash"),
```

Added `validate_model` to `OPENCODE` and `OpenCodeConfig`. Also swapped default review model `kimi-k2.7-code` → `minimax-m3`.

> **Consistency note (2026-08-23):** current `master` default review entry is again `opencode-go/kimi-k2.7-code` (`demetra/settings.py:145`); `minimax-m3` remains default **plan** model.

## Step 3 — Service

**File:** `demetra/services/opencode.py:107`

`opencode_validate_agent(target_path, build_plan, task_title=None, env=None)` mirrors `opencode_review_agent`: loads `validate_agent` prompt, appends build plan, runs with `OPENCODE["validate_model"]`.

## Step 4 — Workflow wiring

**Files:** `demetra/workflows/validate.py` (new), `demetra/workflows/build.py:102`

`run_validate_agent(target_path, build_plan, env)` strips empty/no-issue-token lines, returns `None` on full coverage, raises `BuildError` on non-zero exit. In `run_build_step` between build and review:

```python
await update_session_step(task_id=context.linear_task.id, step="validate")
missing_items = await run_validate_agent(target_path=context.worktree_path, build_plan=build_plan, env=context.project.environment)
if missing_items:
    if context.auto_mode:
        current_task = missing_items; rerun_attempts -= 1; review_attempts -= 1; continue
    result, _ = await user_input([("1", "apply missing plan items"), ("2", "skip")])
```

Auto mode feeds missing items back to build agent (decrementing both counters); interactive skip resets counters and proceeds to review.

## Step 5 — Fix: stdin delivery instead of 4095-char truncation

**Commit `78edceb`.** CodeRabbit findings (plus nits: named args, `parts: list[str]`):

1. **Prompt truncation** — `shlex.quote(task)[:4095]` dropped trailing plan steps. Now delivered via stdin:

   **File:** `demetra/services/opencode.py:213` → `run_command(..., input_text=task)`
   **File:** `demetra/services/subprocess.py:10` — `pipe_stdin_input` + `input_text: str | None` on `run_command` (only opens `stdin=PIPE` when provided).

2. **Silent failure** — non-zero exit could return `None` (treated as success). Now raises `BuildError`.

## Step 6 — Tests

**Files:** `tests/test_validate_workflow.py` (new), additions to `tests/test_opencode.py`, `tests/test_subprocess.py`, `tests/test_workflows.py`, `tests/test_settings.py`, `tests/test_more_edge_cases.py`

Covered: full coverage → `None`, partial → missing items, empty diff → all missing, no-issue-token filtering, non-zero → `BuildError`, stdin piping, `validate_model` settings.

## Test Results

- New/changed test modules for validate workflow, subprocess stdin, settings.
- `make test`, `ruff check`, `ty check`, `pre-commit run --all-files` pass per MNT-146.
- Version `1.15.7` → `1.16.0`.

---

## Follow-ups

- PR #72 merged via `99b5880` (2026-08-05).
- CodeRabbit `COMMENTED` — 2 actionable + 2 nits fixed in `78edceb`.
- Out of scope: correctness/quality/security review, lint/tests, plan/build/review agent changes.

> **Consistency note (2026-08-27):** `demetra/services/opencode.py` → `demetra/services/agents/opencode.py`; `demetra/services/subprocess.py` → `demetra/services/runtime/subprocess.py` (`04436c6`). Stdin-piping behavior unchanged.

## References

- Related: [[2026-02-23-add-multiagent-code-review]], [[2026-03-11-task-plan-summarization]], [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-07-16-fix-step-status-review-findings]], [[2026-07-16-fix-empty-build-plan-loop]]
- Linear: [MNT-146](https://linear.app/mnt/issue/MNT-146/post-build-validation)
- GitHub: [PR #72](https://github.com/manti-by/demetra/pull/72)
