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
related:
- 2026-07-15-duplicated-log-messages.md
- 2026-07-16-fix-step-status-review-findings.md
---

# Simplify setup_session_logging

## TL;DR

Behavior-preserving refactor of `setup_session_logging()` (`demetra/services/utils.py`) after the dedup fix in [[2026-07-15-duplicated-log-messages]]: dropped unused `logger` param (3 call sites), collapsed two handler loops into one `next(...)` lookup, removed dead formatter fallbacks, and anchored the dedup early-return with a comment. 36→27 lines; 472 tests, `ruff`/`ty` clean.

---

## Overview

Two cases: (1) **Subprocess** (`LOG_PATH=sessions/<task>.log`) — root already targets session log, just reuse its handler for `stream_logger` and return (adding another would duplicate, see [[2026-07-15-duplicated-log-messages]]). (2) **In-process** (merge/rebase, `LOG_PATH=demetra.log`) — build new `FileHandler`, swap it onto root and `stream_logger`.

## Changes

- **Drop `logger` param** (`demetra/services/utils.py:75`): `setup_session_logging(logger, task_id)` → `setup_session_logging(task_id)`. Updated `main.py:48`, `demetra/workflows/merge.py:21`, `rebase.py:21`; removed `Logger` import. Kept `async` to avoid touching `AsyncMock` patches.
- **Single handler lookup**: replaced two `for handler in root.handlers` loops with `root_file_handler = next((h for h in root.handlers if isinstance(h, FileHandler)), None)`, reused in both branches.
- **Direct formatter lookup**: `LOGGING["formatters"][file_config["formatter"]]` instead of chained `.get()` with dead fallbacks; session dir became `LOG_DIR if LOG_DIR.name == "sessions" else LOG_DIR / "sessions"`.

## Test Results

472 passed, `ruff`/`ty` clean, no test changes needed.

---

## Follow-ups

None.

> **Consistency note (2026-08-24):** `demetra/services/utils.py` → `demetra/services/runtime/utils.py`.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-15-duplicated-log-messages]]
- Related: [[2026-07-16-fix-step-status-review-findings]]
