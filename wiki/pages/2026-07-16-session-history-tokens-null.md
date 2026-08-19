---
title: Session history tokens always NULL — pipe truncation in opencode export
date: 2026-07-16
type: debug
status: resolved
session_id: ses_0936687abffekKL1uBAPkCWbGU
services: [database, alembic, opencode]
branch: "-"
tickets: []
tags: [session-history, pipe-truncation, opencode-export, debugging]
related: []
---

# Session history tokens always NULL — pipe truncation in opencode export

## TL;DR

Two separate causes were found. On the **local dev DB**, migration `a2b3c4d5e6f7` (adds token columns) was never applied — every INSERT failed silently. On the **odin production server**, the migration *was* applied but all 38 rows still had NULL tokens because `get_opencode_session_tokens` (`opencode export <session_id>`) truncates output at 65,536 bytes when stdout is a subprocess PIPE (OS pipe buffer). The truncated JSON fails to parse → returns `None` → `record_session_history` inserts NULL tokens. Fixed by adding `run_command_to_file` that redirects stdout to a temp file, bypassing the pipe truncation. All 489 tests pass, verified on odin with real token data returned correctly.

---

## Symptom

`session_history` rows always have NULL in all token columns (`input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `length`) even though callers pass usage data.

## Step 1 — Compare DB revision vs. head (local dev)

Ran `alembic current` and `alembic heads`:

| Check | Result |
|---|---|
| `alembic current` | `f1a2b3c4d5e6` (DB revision) |
| `alembic heads` | `a2b3c4d5e6f7` (pending) |

The head revision `a2b3c4d5e6f7` ("add session_history token columns") was never applied.

## Step 2 — Confirm column mismatch (local dev)

DB schema had only `id, session_id, step, length, created_at`; `tables.py:103-107` defines `input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens`. Every INSERT fails with `column "input_tokens" does not exist`.

## Step 3 — Trace silent failure in callers

Every caller wraps `record_session_history` in `try/except (SQLAlchemyError, OSError)`:

- **File:** `demetra/workflows/plan.py:87` — "Failed to record session step history."
- **File:** `demetra/workflows/build.py:38` — silently sets `history = None`
- **File:** `demetra/workflows/cleanup.py:74,95` — "Failed to record session step history, continuing."

## Step 4 — Check odin server (migration already applied)

Connected to `192.168.1.100` — migration IS applied. Table has all token columns. 38 rows exist, but ALL token columns are NULL (including `length`). So `usage` itself is `None` → `get_opencode_session_tokens` returns `None`.

## Step 5 — Isolate the real root cause

`get_opencode_session_tokens` runs `opencode export <session_id>` via `run_command` (`asyncio.subprocess.PIPE`). The output was truncated at exactly 65,536 bytes (the OS pipe buffer). The `export` subcommand checks `isatty()` — when stdout is a PIPE it flushes early and exits, producing only one buffer's worth of output (1.28MB to a file, 64KB to a pipe).

Measured on odin:

| Test | stdout target | bytes captured | JSON parses? |
|---|---|---|---|
| shell `> file` | regular file | 1,281,447 | yes |
| `asyncio.subprocess.PIPE` + `communicate()` | pipe | **65,536** | no (truncated mid-`"msg_f6c8`) |
| `pty.openpty()` | PTY | 1,293,220 | yes |

`json.loads` fails → `get_opencode_session_tokens` returns `None` → all token/length columns NULL.

## Root cause

`opencode export` does not emit its full JSON payload when stdout is a pipe (non-TTY). The 64KB truncation causes `JSONDecodeError` in `get_opencode_session_tokens`, which returns `None`. The NULL propagates through `record_session_history` as token/length=NULL.

## Resolution / Fix

**Local dev:** Apply the migration — `uv run alembic upgrade head`.

**Odin / general fix for pipe truncation:** Added `run_command_to_file` to `demetra/services/subprocess.py` — a new subprocess helper that redirects stdout to a `NamedTemporaryFile` (delete=False), reads it back after the process exits, then deletes the file. Returns the same `tuple[int, str, str]` as `run_command`. Stderr still flows through `live_stream` with existing timeout handling.

**File:** `demetra/services/opencode.py:150` — `get_opencode_session_tokens` now calls `run_command_to_file` instead of `run_command`. Other code paths (`run opencode` etc.) are untouched.

**File:** `demetra/services/subprocess.py` — added `run_command_to_file` function.

### Verified on odin

Backed up + patched the two files on odin, ran `get_opencode_session_tokens` against the real pending session:

```
TokenUsage(input=262843, output=21617, reasoning=23040, cache_read=7934016, cache_write=0)
total: 8241516
```

Originals restored after verification — production still has the buggy code until deployed via git pull.

### Test results

All 489 tests pass. Ruff and ty checks pass. Added `TestSubprocessToFile` (6 tests) covering: file content returned, stdout is NOT a pipe, temp file cleanup, env/cwd forwarding, timeout path, missing-stderr error path. Updated `test_opencode.py` to patch `run_command_to_file`.

---

## Follow-ups

Deploy via git pull to odin. No further code changes needed.

## References

- Related: none
