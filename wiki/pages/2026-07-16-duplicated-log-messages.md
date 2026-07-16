---
title: Duplicated log messages and missing build agent logs
date: 2026-07-16
type: debug
status: resolved
session_id: ses_094983da7ffe4Xk4LIfYPUrftI
services: [main, tui, watcher, build]
branch: -
tickets: []
tags: [logging, duplication, type-bug, build-agent]
related: [2026-07-16-simplify-session-logging-setup.md]
---

# Duplicated log messages and missing build agent logs

## TL;DR

Two logging bugs in the build workflow subprocess: (1) `print_message()` outputs appeared duplicated in session log files because `setup_session_logging()` had a dedup guard comparing `Path` to `str` (always `False`), letting a second `FileHandler` be added to `tui_logger` with `propagate=True`. (2) The build agent's `stdout` was captured but discarded on success — it never entered the logging framework, so build agent output was absent from session logs entirely.

---

## Issue 1 — Duplicated `print_message` outputs

### Symptom

Session log files on the odin server contained duplicate entries:

```
2026-07-16 17:46:51 INFO  : Running BUILD agent
2026-07-16 17:46:51 INFO  : Running BUILD agent
2026-07-16 17:48:15 INFO  : Running REVIEW agents
2026-07-16 17:48:15 INFO  : Running REVIEW agents
```

Only `print_message()` calls duplicated — other loggers (which propagate solely to root) wrote once.

### Step 1 — Ruling out initial hypotheses

**Hypothesis A — `dictConfig` called twice:** `demetra/settings.py` calls `dictConfig(LOGGING)`, and `main.py:17` re-imports settings (which re-runs `dictConfig`). Empirically verified: `dictConfig` is idempotent — it clears and replaces handlers each call. Not the cause.

**Hypothesis B — Two concurrent subprocesses:** The watcher and listener could both enqueue the same build task. But duplication appears within a single session log file, not across files. Ruled out.

### Step 2 — Tracing the subprocess logging setup

The build workflow spawns `main.py` as a subprocess via `demetra/services/watcher.py:45`:

```python
env["LOG_PATH"] = f"sessions/{task_id}.log"
```

So in the child `main.py`:
1. `settings.py:66` sets `LOGGING["handlers"]["file"]["filename"] = LOG_PATH` → a `Path` object
2. `dictConfig(LOGGING)` configures the **root logger** with a `FileHandler` pointing at the session log
3. `main.py:48` calls `setup_session_logging()`, which has a dedup guard at `demetra/services/utils.py:78`:
   ```python
   if LOGGING["handlers"]["file"]["filename"] == str(session_log_path):
       return
   ```
4. `session_log_path` is the resolved `Path` passed as argument

### Root cause

**`Path == str` is always `False` in Python.** `LOGGING["handlers"]["file"]["filename"]` is a `Path` (set via `LOG_PATH` in `settings.py:66`). `str(session_log_path)` is a string. The comparison never evaluates to `True`, so the guard never fires.

`setup_session_logging()` then attaches a second `FileHandler` (same session file) to `demetra.services.tui`. Since `tui_logger.propagate` is `True`, every `print_message` → `tui_logger.info()` is written **twice**: once by `tui_logger`'s own handler, once by the root handler via propagation.

Only `print_message` outputs duplicate because `tui_logger` is the only logger that gets the extra handler. Merge/rebase workflows run in-process with `LOG_PATH=demetra.log` — `session_log_path` differs from the root's target so the guard correctly falls through and they get their own per-session handler (one write).

### Resolution — Issue 1

**File:** `demetra/services/utils.py:78`

Before:
```python
if LOGGING["handlers"]["file"]["filename"] == str(session_log_path):
```

After:
```python
if Path(LOGGING["handlers"]["file"]["filename"]).resolve() == session_log_path.resolve():
```

Both sides are now `Path` objects, and `.resolve()` normalizes any relative/absolute mismatch. The early-return fires correctly when the root handler already targets the session log.

---

## Issue 2 — Missing build agent logs in session files

### Symptom

Session log files contained `print_message` entries from the plan agent ("Plain plan agent output:...") but no corresponding build agent output, even though the build agent ran and produced output visible on `stdout`.

### Root cause

**File:** `demetra/workflows/build.py:64-74`

The plan agent logs its output via `print_message` in `plan.py:35`:
```python
print_message(f"Plain plan agent output:\n{plan_output}", style="info")
```

But the build agent's output was captured but discarded on success:
```python
exit_code, stdout, stderr = opencode_build_agent(...)
if exit_code != 0:
    print_message(f"Build agent failed:\n{stderr}", style="error")
    return None, stderr
return None, None  # stdout silently dropped
```

The `stdout` went to `sys.stdout` via `live_stream` (reaching `demetra.log` through the watcher's pipe capture) but never entered the logging framework, so it never appeared in session log files.

### Resolution — Issue 2

**File:** `demetra/workflows/build.py:71`

Added a `print_message` call matching the plan agent pattern after the build agent succeeds:

```python
if exit_code != 0:
    print_message(f"Build agent failed:\n{stderr}", style="error")
    return None, stderr
print_message(f"Build agent output:\n{stdout.strip()}", style="info")
return None, None
```

---

## Verification

All 472 tests pass, `ruff check` and `ty check` clean. No test changes needed — `setup_session_logging` is mocked in all tests and the build workflow test mocks the agent call.

---

## Follow-ups

- None

## References

- Related: [[2026-07-16-simplify-session-logging-setup]] — later behavior-preserving refactor of `setup_session_logging()`
