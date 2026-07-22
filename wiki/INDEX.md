# demetra Wiki — Index

Session knowledge base for the demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added FEATURES dict with IS_RUFF_ENABLED/IS_PYTEST_ENABLED env flags, gated lint workflow, added 6 new tests (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Debug: Rich `MarkupError` from a review finding with `[/.../]` regex crashed the workflow subprocess; escape markup in `print_message` and only increment `run_attempts` on actual failure (2026-07-21)
- [<title>](pages/2026-07-21-socket-server.md) — (2026-07-21)
- [Fixing Failing Tests](pages/2026-07-21-fixing-failing-tests.md) — Fixed two failing tests by updating their expected behavior and renaming the test methods. (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Fixed ANSI coloring issues by adding stripping filters at four levels in logging pipeline (2026-07-20)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Guarded mark_notification_read with success bool and added listener_attempts counter with MAX_LISTENER_ATTEMPTS=3 to break infinite retry loops (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Implementation: unified StepType/VALID_STEPS enum, renamed API `status`→`step`, fixed stale `upsert_pending_session` return value, documented divergent ON CONFLICT clauses (2026-07-16)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging.md) — Implementation: behavior-preserving refactor — dropped unused `logger` param, single root-handler lookup, removed dead formatter fallbacks (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Implementation: replan on missing build_plan (not step), validate Linear response payload, enable fallback session ID recovery (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-16-duplicated-log-messages.md) — Path==str dedup bug causing double writes, plus build agent stdout discarded instead of logged (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Debugged pipe truncation in opencode export causing NULL token columns; fixed with run_command_to_file temp-file approach (2026-07-16)
_Newest first._

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### ANSI escape codes in logs (1 page)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — ANSI stripping filters at four levels in logging pipeline

### Logging infrastructure (2 pages)

- [Duplicated log messages and missing build agent logs](pages/2026-07-16-duplicated-log-messages.md) — Path==str dedup bug causing double writes, build agent stdout discarded
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Behavior-preserving refactor of setup_session_logging

### Build plan / workflow crashes (2 pages)

- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Replan on missing build_plan, validate Linear payload, enable fallback session ID
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Rich `MarkupError` from review finding crashed subprocess; escape markup, only increment `run_attempts` on failure

### Notification / listener (1 page)

- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Mark-as-read gating and listener_attempts counter

### Watcher / tui rendering (1 page)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — `print_message` now escapes Rich markup; `run_attempts` only counted on failure

### Step/status refactor (1 page)

- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Unified StepType, renamed API status→step, fixed upsert return value

### Session history tokens (1 page)

- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Pipe truncation in opencode export causing NULL token columns
