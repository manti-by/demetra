---
title: Simplify setup_session_logging
date: 2026-07-16
type: implementation
status: resolved
session_id: 3829832e-7a27-42ce-8897-f46a971a95a4
services: [main, merge, rebase]
branch: "-"
tickets: []
tags: [logging, refactoring, cleanup]
related: [2026-07-15-duplicated-log-messages.md, 2026-07-16-fix-step-status-review-findings.md]
---

# Simplify setup_session_logging

## TL;DR

Refactored `setup_session_logging()` in `demetra/services/utils.py` — it had grown hard to read
after the dedup fix from [[2026-07-15-duplicated-log-messages]]. Behavior is unchanged: dropped the
unused `logger` parameter (updating three call sites), collapsed duplicate handler loops into a
single lookup, removed dead defensive fallbacks in the formatter lookup, and documented *why* the
early-return dedup branch exists. Function went from 36 to 27 lines; all 472 tests pass, `ruff` and
`ty` clean.

---

## Overview

The function does two things depending on whether the root logger's `FileHandler` already targets
the per-task session log:

1. **Subprocess case** (build workflow spawns `main.py` with `LOG_PATH=sessions/<task>.log`):
   root already writes to the session log — just attach the existing handler to `stream_logger`
   and return. Adding a second handler here is exactly the duplicate-message bug fixed in
   [[2026-07-15-duplicated-log-messages]].
2. **In-process case** (merge/rebase workflows, `LOG_PATH=demetra.log`): build a new session
   `FileHandler`, swap it in for the root's current one, and attach it to `stream_logger` too.

The refactor makes those two cases read as two clear branches without changing what either does.

## Step 1 — Drop the unused `logger` parameter

The `logger: Logger` parameter was never referenced in the body — the function only touches the
root logger and the module-level `stream_logger`.

**File:** `demetra/services/utils.py:75`

Before:
```python
async def setup_session_logging(logger: Logger, task_id: str) -> None:
```

After:
```python
async def setup_session_logging(task_id: str) -> None:
```

Updated the three call sites and removed the now-unused `Logger` import:

- `main.py:48` — `await setup_session_logging(task_id=context.linear_task.id)`
- `demetra/workflows/merge.py:21` — `await setup_session_logging(task_id=session.task_id)`
- `demetra/workflows/rebase.py:21` — `await setup_session_logging(task_id=session.task_id)`

Tests patch the function with `AsyncMock` at each call-site module, so no test changes were needed.

## Step 2 — Single root-handler lookup instead of two loops

The old code iterated `root_logger.handlers` twice — once in the dedup branch to find the handler
to reuse, and once in the swap branch to remove old `FileHandler`s. The new code finds the root
`FileHandler` once with `next(...)` and uses it in both branches (the `dictConfig` in
`settings.py` only ever installs one file handler on root).

Before:
```python
if configured_filename.resolve() == session_log_path.resolve():
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            stream_logger.addHandler(handler)
            break
    return
...
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        handler.close()
        root_logger.removeHandler(handler)
```

After:
```python
root_file_handler = next((h for h in root_logger.handlers if isinstance(h, logging.FileHandler)), None)

if Path(file_config["filename"]).resolve() == session_log_path.resolve():
    # Root already writes to the session log — adding another handler would
    # duplicate every propagated record. Reuse it for the stream logger.
    if root_file_handler is not None:
        stream_logger.addHandler(root_file_handler)
    return
...
if root_file_handler is not None:
    root_file_handler.close()
    root_logger.removeHandler(root_file_handler)
```

The comment on the early return anchors the dedup guard to its reason, so the branch doesn't get
"simplified away" again in a future cleanup.

## Step 3 — Direct formatter lookup, session-dir one-liner

`settings.py` always defines the `standard` formatter with both `format` and `datefmt`, so the
chain of `.get()` calls with fallbacks was a dead path.

Before:
```python
formatter_name = LOGGING["handlers"]["file"].get("formatter")
formatter_config = LOGGING.get("formatters", {}).get(formatter_name, {})
fmt = Formatter(
    fmt=formatter_config.get("format"),
    datefmt=formatter_config.get("datefmt"),
)
```

After:
```python
formatter_config = LOGGING["formatters"][file_config["formatter"]]
file_handler.setFormatter(Formatter(fmt=formatter_config["format"], datefmt=formatter_config["datefmt"]))
```

The four-line `if/else` computing `session_dir` also became a conditional expression:
```python
session_dir = LOG_DIR if LOG_DIR.name == "sessions" else LOG_DIR / "sessions"
```

## Test Results

- `uv run pytest -q` — **472 passed** in 8.4s, no test changes needed.
- `uv run ruff check .` — clean.
- `uv run ty check` — clean.

Deliberately kept the function `async` (it has no awaits) so the three call sites and their
`AsyncMock` patches stayed untouched.

---

## Follow-ups

- None

> **Consistency note (2026-08-24, Consistency Agent):** Module paths in this session record have moved — demetra/services/utils.py → demetra/services/runtime/utils.py. Historical `file:line` refs below are kept as written.

## References

- Related: [[2026-07-15-duplicated-log-messages]]
- Related: [[2026-07-16-fix-step-status-review-findings]] — later code review of the same diff, covering sessions.step/status handling
