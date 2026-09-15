---
title: Duplicated log messages and missing build agent logs
date: 2026-07-15
type: debug
status: resolved
session_id: ses_094983da7ffe4Xk4LIfYPUrftI
services: [main, tui, watcher, build]
branch: "-"
tickets: []
tags: [logging, duplication, type-bug, build-agent]
related: [2026-07-16-simplify-session-logging-setup.md]
---

# Duplicated log messages and missing build agent logs

## TL;DR

Two build-workflow logging bugs fixed: (1) `print_message()` lines duplicated in session logs because `setup_session_logging()` compared `Path` to `str` (always `False`), adding a second `FileHandler` to `tui_logger` with `propagate=True`. Fixed by comparing `Path.resolve()` on both sides. (2) Build agent `stdout` was captured but discarded on success — never reached the logging framework. Fixed by adding a `print_message` call on success matching the plan agent pattern.

---

## Issue 1 — Duplicated `print_message` outputs

### Symptom

Session logs showed duplicate lines (e.g. `Running BUILD agent` twice). Only `print_message()` duplicated — other loggers propagate solely to root.

### Hypotheses ruled out

- **`dictConfig` twice** (`demetra/settings.py` + `main.py:17` re-import): `dictConfig` is idempotent (clears/replaces handlers). Not the cause.
- **Concurrent subprocesses**: duplication is within a single log file, not across files.

### Root cause

Subprocess sets `LOG_PATH=sessions/<task>.log` (`demetra/services/watcher.py:45`), then `main.py:48` calls `setup_session_logging()`. Guard at `demetra/services/utils.py:78`:

```python
if LOGGING["handlers"]["file"]["filename"] == str(session_log_path):
```

`LOGGING[...]["filename"]` is a `Path` (set in `settings.py:66`); `str(session_log_path)` is a string — `Path == str` is always `False`, so a second `FileHandler` is added to `tui_logger` with `propagate=True` → each `print_message` written twice. Merge/rebase run in-process with `LOG_PATH=demetra.log` so the guard correctly falls through there.

### Resolution

`demetra/services/utils.py:78` — compare `Path` to `Path`:

```python
if Path(LOGGING["handlers"]["file"]["filename"]).resolve() == session_log_path.resolve():
```

---

## Issue 2 — Missing build agent logs

### Symptom

Plan agent output appeared (via `print_message` in `plan.py:35`) but build agent output was absent from session logs.

### Root cause

`demetra/workflows/build.py:64-74` — build agent `stdout` discarded on success:

```python
exit_code, stdout, stderr = opencode_build_agent(...)
if exit_code != 0:
    print_message(f"Build agent failed:\n{stderr}", style="error")
    return None, stderr
return None, None  # stdout dropped
```

`stdout` reached `demetra.log` via `live_stream` pipe but never entered logging framework for session files.

### Resolution

`demetra/workflows/build.py:71` — log on success:

```python
print_message(f"Build agent output:\n{stdout.strip()}", style="info")
```

---

## Verification

472 tests pass, `ruff`/`ty` clean. No test changes — `setup_session_logging` mocked, build agent mocked.

---

## Follow-ups

None.

> **Consistency note (2026-08-24):** `demetra/services/utils.py` → `demetra/services/runtime/utils.py`.

## References

- Related: [[2026-07-16-simplify-session-logging-setup]]
