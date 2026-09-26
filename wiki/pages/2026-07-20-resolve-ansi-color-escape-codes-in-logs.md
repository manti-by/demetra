---
title: Resolve ANSI Color Escape Codes in Logs
date: 2026-07-20
type: debug
status: resolved
session_id: ses_080257f1affen6vKaLZQEZglVY
services: [main]
branch: "-"
tickets: []
tags: [logs, filtering, ansi, coloring-issues]
related: []
---

# Resolve ANSI Color Escape Codes in Logs

## TL;DR

Raw ANSI escape sequences (`\x1b[31m` etc.) in logs rendered as garbled text. Fixed by adding stripping via regex `\x1b\[[0-9;]*[a-zA-Z]` at source and in the logging config, covering all handlers.

---

## Symptom

Logs contained raw ANSI escapes that polluted log viewers and files.

## Resolution

- `demetra/services/utils.py:12-22` — `AnsiStrippingFilter` + `ansi_strip` helper (regex `\x1b\[[0-9;]*[a-zA-Z]`).
- `demetra/services/utils.py:57` — stripped at source in `live_stream()` before subprocess output is logged.
- `demetra/settings.py:52-56, 68, 75` — registered in `LOGGING` dictConfig on both `console` and `file` handlers (covers `print_message`).
- `demetra/services/utils.py:109` — applied to dynamically created session handlers in `setup_session_logging()`.

## Verification

No ANSI escapes remain in log output.

---

## Follow-ups

None.

> **Consistency note (2026-08-24):** `demetra/services/utils.py` → `demetra/services/runtime/utils.py`.

## References

- Related: none
