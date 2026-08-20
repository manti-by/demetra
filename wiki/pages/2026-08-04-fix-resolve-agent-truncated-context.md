---
title: Plan loop resolve agent received truncated context
date: 2026-08-04
type: debug
status: resolved
session_id: "-"
services: [opencode, workflows]
branch: "-"
tickets: []
tags: [plan-loop, resolve-agent, opencode, task-delivery, arg-max, shlex]
related: [2026-06-02-plan-loop-resolve-questions.md, 2026-07-16-session-history-tokens-null.md, 2026-08-05-post-build-validation.md]
---

# Plan loop resolve agent received truncated context

## TL;DR

In `--auto --plan-loop` mode, the resolve agent was being handed only a truncated original task with no question list because `run_opencode_agent` passed the task as a `shlex.quote(task)[:4095]` positional argument. The 4 095-character cap (Python string slicing counts characters, not bytes) was a silent defence against `ARG_MAX`; the rendered `resolve_questions` prompt (template + original task + numbered questions) routinely crosses it, and the questions — sitting at the tail of the prompt — are the first thing sliced off. Fix: drop the `[:4095]` cap. The OS `ARG_MAX` (~1 MB on macOS, ~2 MB on Linux) is the real limit, and is well above any realistic Linear ticket + prompt in practice. The first attempt of the fix swapped the positional arg for a temp file via `opencode run --file`; that broke every agent with `Error: You must provide a message or a command` because `--file` is an attachment, not a message substitute. Reverted to the positional-arg path.

---

## Symptom

Auto-mode run with a Linear ticket whose description + plan-agent questions exceeded 4 KB printed:

```text
● Plan loop enabled, sending questions to RESOLVE agent (attempts left: 9).
● Running RESOLVE agent
> resolve-agent · gpt-5.6-sol

Please provide the planning agent's open questions. The message currently includes only a truncated original task and no question list.
```

Every iteration of the plan loop lost the questions, so the resolve agent refused to act and the loop wasted an attempt.

> **Status update (2026-08-06, Consistency Agent):** the positional-argument delivery
> described below was later superseded — PR #72 (MNT-146, commit `78edceb`) replaced it
> with stdin piping (`run_command(input_text=task)`), removing the argv-bound
> transport entirely. See [[2026-08-05-post-build-validation]] Step 5.

## Step 1 — Reproduce the math

The resolve-agent task is built in `demetra/workflows/resolve.py:23-28` as a `get_prompt("resolve_questions", ...)` render. The template (`demetra/prompts/resolve_questions.md`, ~890 chars) appends `numbered_questions` last:

**File:** `demetra/prompts/resolve_questions.md:8-11`

```markdown
Open Questions to Resolve:
<numbered_questions>
{numbered_questions}
</numbered_questions>
```

For a normal Linear ticket (3 KB description) + 5 plan-agent questions (~1 KB), the rendered task is ~4 900 characters before `shlex.quote`. With shell escaping it crosses ~5 000 characters — well past the 4 095-character cap. The numbered questions sit at the tail of the prompt, so they are the first thing sliced off.

## Step 2 — Locate the cap

**File:** `demetra/services/opencode.py:184` (before the fix)

```python
command.append(shlex.quote(task)[:4095])
```

The `[:4095]` was added in commit `b43f542` ("Remove TY, update utils, update README.md and AGENTS.md", 2026-02-21) presumably as a defensive guard against `ARG_MAX`. The cap is silent — neither a warning nor an error — so the resolve agent had no way to tell that content was dropped. It just saw a shorter-than-expected prompt and refused to act.

## Root cause

`shlex.quote(task)[:4095]` is a silent upper bound on every agent task — plan, build, merge, resolve, anything that flows through `run_opencode_agent`. For most calls the task is short, so the bug was invisible. It only surfaced in plan-loop mode, where the resolve-agent prompt is the only one that *guarantees* a long tail (the numbered questions), and where the failure mode (resolve-agent asking for the questions) is uniquely visible.

## Step 3 — First fix attempt (rejected)

Tried replacing the positional arg with a temp file passed via `opencode run --file`. Opencode's help confirms the flag exists:

```text
-f, --file         file(s) to attach to message                                            [array]
```

But the word **attach** is load-bearing: `--file` supplements the message, it does not replace it. Running `opencode run --file /tmp/msg.md` with no positional message produces:

```text
Error: You must provide a message or a command
```

Every agent (build, plan, resolve, review, merge) failed identically, so the file-based path was reverted.

## Resolution / Fix

**File:** `demetra/services/opencode.py:184-189`

- Reverted to passing the task as a positional argument; dropped the `[:4095]` cap. The transport bounds are the host's exec limits: `ARG_MAX` (~1 MB on macOS, ~2 MB on Linux) for the combined argv + environment, and Linux's 128 KB `MAX_ARG_STRLEN` per single argument. Both are well above any realistic Linear ticket + prompt in practice.
- Updated the `run_opencode_agent` docstring to record the `[:4095]` history so the cap is not re-introduced in a future refactor.

**File:** `tests/test_opencode.py`

- Reverted `test_run_opencode_agent_uses_correct_command` to assert the task is the last positional command token.
- Added `test_run_opencode_agent_passes_full_task_without_truncation` (20 000-char task with newlines and quotes; asserts the raw task arrives verbatim as the positional argument) — the regression guard for this bug.

## Verification

```text
$ uv run pytest tests/ -q
============================= 586 passed in 2.77s ==============================
$ uv run ruff check .
All checks passed!
$ uv run ty check
All checks passed!
$ uv run pre-commit run --files demetra/services/opencode.py tests/test_opencode.py
... all hooks Passed
```

End-to-end smoke (mocked subprocess) with a 3 000-char original task + 5 questions:

```text
Task length: 3991 chars
Command args: 9 tokens, last arg length: 3993 chars
PASS: full task delivered (original + all 5 questions)
```

Without the fix this same input would have been clipped at 4 095 chars, dropping the question list.

## Known follow-up (not fixed this session)

- The 4 095 cap was effectively a hard limit on every `run_opencode_agent` caller. With the cap removed, the only limits are `ARG_MAX` and Linux's per-argument `MAX_ARG_STRLEN`. If a future ticket ever produces a multi-MB prompt (very unlikely), `asyncio.create_subprocess_exec` fails with `OSError` (`E2BIG`, `Argument list too long`), which `main.py` catches as an "OS Error" and reports to the console — verified in the code path, not left to a shell-level diagnostic.
- Any future agent CLI that requires a positional `message` and supports `--file` as an attachment is a hazard for the same kind of refactor; the lesson is to always pass a real message, not just an attachment.

---

## Follow-ups

- None.

## Consistency note (2026-08-19)

- The positional-arg fix described in the Resolution was itself superseded by PR #72 (MNT-146), which switched to **stdin piping** (`input_text=task` passed to `run_command`). The current `run_opencode_agent` in `demetra/services/agents/opencode.py` delivers the task via stdin, not as a positional argument. No `[:4095]` cap and no `ARG_MAX` concern.

## References

- Related: [[2026-06-02-plan-loop-resolve-questions]], [[2026-08-05-post-build-validation]] (validate-agent that superseded the positional-arg path with stdin piping)
- Related: [[2026-07-16-session-history-tokens-null]] — same pattern (`run_command_to_file`) for handling size-bounded subprocess I/O, but on stdout.
- External: `opencode run --help` (documents the `--file` flag and the positional `message` requirement).
