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
related: [2026-07-23-session-tokens-audit-revalidation.md, 2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-opencode-v2-session-token-accounting.md]
---

# Session history tokens always NULL — pipe truncation in opencode export

## TL;DR

Two causes for NULL `session_history` tokens: the local DB was missing migration `a2b3c4d5e6f7` (every INSERT failed silently), and on odin prod the migration was applied but all 38 rows still had NULL because `opencode export` truncates to 64 KB when stdout is a PIPE. Fixed with `run_command_to_file` (temp-file redirect, bypassing pipe buffer). 489 tests pass; verified on odin with real token data.

---

## Symptom

All `session_history` token columns (`input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `length`) were NULL.

## Diagnosis

- **Local dev**: `alembic current` was `f1a2b3c4d5e6`; head `a2b3c4d5e6f7` ("add token columns") never applied. DB had only `id/session_id/step/length/created_at`; every INSERT failed with `column "input_tokens" does not exist`, silently caught by `try/except (SQLAlchemyError, OSError)` in `plan.py:87`/`build.py:38`/`cleanup.py:74,95`.
- **Odin prod**: migration applied, 38 rows existed, but all tokens NULL → `get_opencode_session_tokens` returns `None`. `opencode export` via `asyncio.subprocess.PIPE` was truncated to exactly **65,536 bytes** (OS pipe buffer; `isatty()` check flushes early), producing mid-JSON truncation → `json.loads` fails → `None` → NULL columns.

| Target | Bytes | JSON parses? |
|---|---|---|
| shell `> file` | 1,281,447 | yes |
| `PIPE` + `communicate()` | 65,536 | no (truncated mid-`"msg_f6c8`) |
| `pty.openpty()` | 1,293,220 | yes |

## Resolution

- **Local dev**: `uv run alembic upgrade head`.
- **General fix** (`demetra/services/subprocess.py`): added `run_command_to_file` — redirects stdout to `NamedTemporaryFile` (delete=False), reads back after exit, deletes file; same `tuple[int,str,str]` return. Stderr still via `live_stream`.
- **`demetra/services/opencode.py:150`**: `get_opencode_session_tokens` now calls `run_command_to_file` instead of `run_command`.

Verified on odin after patching: `TokenUsage(input=262843, output=21617, reasoning=23040, cache_read=7934016, cache_write=0)` total 8241516.

## Test Results

489 tests pass, `ruff`/`ty` clean. New `TestSubprocessToFile` (6 tests: file content, not-a-pipe, cleanup, env/cwd, timeout, missing-stderr). `test_opencode.py` updated to patch `run_command_to_file`.

---

## Update — 2026-10-16 15:08

**The 64 KB story is subcommand-specific, not a uniform cap.** Re-probed on opencode v2.0.30: `session list --format json -n 500` piped **140,107 bytes byte-identical** to the file redirect and parsed cleanly, while `session export <id>` piped **393,216 bytes** (exactly 6 × 65,536) vs **437,195** to a file, with the piped bytes invalid JSON. So the fix here is still correct and still mandatory for export, but the failure class is not "every opencode command truncates at 64 KB".

**The export command itself changed on v2.** `opencode export <id>` moved to `opencode session export <id>`; `get_opencode_session_export` is now version-aware (cached `opencode --version` major) and falls back to trying both forms when the probe fails, while staying **file-backed** (`run_command_to_file`). See [[2026-10-16-mnt-251-session-attribution-accounting]] and the v2 ground truth in [[2026-10-16-opencode-v2-session-token-accounting]].

---

## Follow-ups

Deploy via git pull to odin.

> **Consistency note (2026-08-27):** `demetra/services/subprocess.py` → `demetra/services/runtime/subprocess.py`, `demetra/services/opencode.py` → `demetra/services/agents/opencode.py:355`; fix still in effect.
>
> **Consistency note (2026-10-08, Dedup Agent):** this fix is re-audited as a solved sub-claim in [[2026-07-23-session-tokens-audit-revalidation]] (192-row DB analysis; "truncation confirmed… Solved; no action").

## References

- Related: [[2026-07-23-session-tokens-audit-revalidation]]
