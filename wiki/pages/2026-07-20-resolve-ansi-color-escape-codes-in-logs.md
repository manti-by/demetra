---
title: Resolve ANSI Color Escape Codes in Logs
date: 2026-07-20
type: debug
status: resolved
session_id: ses_080257f1affen6vKaLZQEZglVY
services: [main]
branch: -
tickets: []
tags: [logs, filtering, ansi, coloring-issues]
related: []
---

## TL;DR

ANSI escape codes in logs were causing coloring issues. Fixed by adding a stripping filter at multiple levels.

## Symptom

Logs contained raw ANSI escape sequences (e.g., `\x1b[31m`) that rendered as garbled text in log viewers and files.

## Resolution

Applied ANSI stripping filtering in four places:

1. **`demetra/services/utils.py:12-22`** — `AnsiStrippingFilter` class and `ansi_strip` helper using regex `\x1b\[[0-9;]*[a-zA-Z]` to strip all ANSI escape codes.

2. **`demetra/services/utils.py:57`** — Strip at source in `live_stream()` before subprocess output is logged.

3. **`demetra/settings.py:52-56, 68, 75`** — Register filter in `LOGGING` dictConfig, applied to both `console` and `file` handlers so all log records (including those from `print_message`) are filtered.

4. **`demetra/services/utils.py:109`** — Filter applied to dynamically created session log handlers in `setup_session_logging()`.

## Verification

No colored escape sequences remain in log output.

## Known follow-up

None

## References

- Related: none
