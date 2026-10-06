---
title: Plan loop resolve agent received truncated context
date: 2026-08-04
type: debug
status: resolved
session_id: '-'
services:
- opencode
- workflows
- main
- subprocess
branch: '-'
tickets:
- MNT-79
- MNT-105
tags:
- plan-loop
- resolve-agent
- opencode
- task-delivery
- arg-max
- shlex
- questions
- auto
- cwd
- worktree
- context
- bug
related:
- 2026-06-02-plan-loop-resolve-questions.md
- 2026-07-16-session-history-tokens-null.md
- 2026-08-05-post-build-validation.md
- 2026-06-03-context-bloating.md
- 2026-07-16-fix-empty-build-plan-loop.md
---
# Plan loop resolve agent received truncated context

## TL;DR

In `--auto --plan-loop`, the resolve agent received a truncated task with no questions because `run_opencode_agent` did `shlex.quote(task)[:4095]` — a silent 4095-char cap (Python string slice, not bytes) guarding `ARG_MAX`. The rendered `resolve_questions` prompt (template ~890 chars + ticket + numbered questions at the tail) routinely exceeds it, so questions were sliced off. Fixed by dropping the cap; `ARG_MAX` (~1 MB macOS, ~2 MB Linux) is well above any real ticket. A `--file` temp-file attempt failed (`--file` is an attachment, not a message — `Error: You must provide a message`) and was reverted. Later superseded by stdin piping (PR #72).

## Symptom

```
● Plan loop enabled, sending questions to RESOLVE agent (attempts left: 9).
● Running RESOLVE agent
> resolve-agent · gpt-5.6-sol
Please provide the planning agent's open questions. The message currently includes only a truncated original task…
```

Every plan-loop iteration lost questions and wasted an attempt.

> **Status (2026-08-06):** Positional-arg delivery superseded by PR #72 (MNT-146, `78edceb`) → stdin piping (`run_command(input_text=task)`). See [[2026-08-05-post-build-validation]].

## Cause

**`demetra/services/opencode.py:184`** (pre-fix): `command.append(shlex.quote(task)[:4095])` — added in `b43f542` (2026-02-21) as `ARG_MAX` guard, silent truncation. Template `demetra/prompts/resolve_questions.md:8-11` puts `numbered_questions` last; a 3 KB ticket + 5 questions (~1 KB) → ~4900 chars rendered, ~5000 quoted — questions at tail sliced first. All `run_opencode_agent` callers were capped, but only resolve-agent's prompt guarantees a long tail.

## Fix attempts

- **`--file` temp file** (`opencode run --file /tmp/msg.md`): `opencode run -f` is `file(s) to attach [array]` — requires a positional message; without one every agent failed with `Error: You must provide a message`. Reverted.

- **Final fix** (`demetra/services/opencode.py:184-189`): revert to positional arg, drop `[:4095]`. Real limits are `ARG_MAX` (~1 MB / ~2 MB) and `MAX_ARG_STRLEN` 128 KB — well above any ticket. Updated docstring to record `[:4095]` history.

**`tests/test_opencode.py`:** reverted `test_run_opencode_agent_uses_correct_command` + added `test_run_opencode_agent_passes_full_task_without_truncation` (20k-char task with quotes/newlines, asserts verbatim delivery).

## Verification

```
pytest: 586 passed  ruff/ty/pre-commit: clean
Smoke (3000-char task + 5 questions): 3991 chars → 9 tokens, last arg 3993 chars — PASS (would have been clipped at 4095)
```

## Follow-ups

- None. With cap removed, multi-MB prompt would hit `OSError: E2BIG` from `asyncio.create_subprocess_exec`, caught as "OS Error" in `main.py`.
- Lesson: `--file` is attachment, always pass a real message.

## Source — [[2026-06-02-plan-loop-resolve-questions]]

Plan-loop resolve agent (`.opencode/agents/resolve-agent.md`, `--plan-loop`, `MAX_PLAN_ATTEMPTS` 30) — MNT-105, 2026-06-02.

## Source — [[2026-06-03-context-bloating]]

Agents run with worktree as `cwd`/`target_path` — fixed 2026-06-03.

> **Consistency (2026-08-19):** Positional-arg fix superseded by PR #72 stdin piping (`demetra/services/agents/opencode.py`, `input_text=task`).

> **Consistency (2026-08-24):** `demetra/services/opencode.py` → `demetra/services/agents/opencode.py`.

## References

- Related: [[2026-06-02-plan-loop-resolve-questions]], [[2026-07-16-session-history-tokens-null]], [[2026-08-05-post-build-validation]], [[2026-06-03-context-bloating]], [[2026-07-16-fix-empty-build-plan-loop]]
- External: `opencode run --help` (`--file` + positional `message`)
