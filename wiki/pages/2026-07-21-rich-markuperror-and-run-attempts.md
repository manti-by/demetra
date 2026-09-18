---
title: Rich MarkupError kills workflow subprocess and run_attempts counter overcounts
date: 2026-07-21
type: debug
status: resolved
session_id: "-"
services: [watcher, tui, main, database, workflows, linear]
branch: "-"
tickets: [MNT-136, MNT-17, MNT-100]
tags: [rich, markup, tui, watcher, run-attempts, error-handling, agents, cli, textual, investigation, guard, sessions, linear]
related:
- 2026-02-14-add-tui-support.md
- 2026-06-08-max-run-attempts-for-a-ticket.md
---

# Rich MarkupError kills workflow subprocess and run_attempts counter overcounts

## TL;DR

MNT-136 hit `Max run attempts reached` after three identical crashes. A review finding containing `[/^\/admin/, ...]` was passed raw to `demetra.services.tui.print_message`, where Rich parsed `[/...]` as a closing tag and raised `MarkupError`, killing the subprocess with empty stderr. Every watcher invocation also incremented `run_attempts`, so one real failure mode consumed the budget. Fixed by escaping Rich markup in `print_message` and incrementing only on actual failure.

## Symptom

- MNT-136 in `Awaiting Input` with "Max run attempts reached"; DB `sessions.run_attempts=4`, `step="failed"` (`4c32355e-55bf-478f-8cd6-832bacafe6f9`).
- Watcher log: `WARNING: Max run attempts (3) reached for task 4c32355e-…` (`demetra.log:390177`).
- Each prior run: `ERROR: Workflow failed for task … :` (empty stderr) then `Moving back a ticket in TODO` — non-zero exit with no captured error.
- Sibling MNT-138 in same run succeeded (PR #22) — failure was specific to MNT-136's review findings.

## Cause 1 — Rich MarkupError

Traceback (`demetra.log:353928`, `390169`):

```
rich.errors.MarkupError: closing tag '[/^\/admin/, /^\/api/]' at position 476 doesn't match any open tag
```

The string came from `demetra/workflows/review.py:43-44`:

```python
findings_text = "\n".join(f"{i+1}. {finding}" for i, finding in enumerate(meaningful))
print_message(findings_text, style="result")
```

The finding suggested `denylist: [/^\/admin/, /^\/api/, /^\/static/, /^\/media/]` (`4c32355e-…log:27093`). `demetra/services/tui.py:16-33` passed it raw to `console.print(message, style=…)` where `[/...]` is parsed as a closing tag. `rich.markup.escape('[/^\\/admin/]')` → `'\\[/^\\/admin/]'` — escaping `[` is sufficient.

Stderr was empty because the traceback fires during `console.print` after `process.communicate()` already consumed subprocess stderr.

## Cause 2 — `run_attempts` overcount

`demetra/services/watcher.py:32` (pre-fix) did `attempts = await increment_run_attempts(task_id)` before the run, then checked `attempts > MAX_RUN_ATTEMPTS`. Every watcher call — success, auto-cancel, or failure — burned a slot. The first run was an `AutoCancelledError` (plan agent emitted 5 open questions, `plan.py:119-129`), yet it counted as attempt 1. With `MAX_RUN_ATTEMPTS=3` (override; default 5 in `settings.py:37`), 1 auto-cancel + 2 MarkupErrors → 4th call bailed (`attempts=4 > 3`).

## Resolution

### Fix 1 — Escape Rich markup (`demetra/services/tui.py:4, 17-35`)

```python
from rich.markup import escape
safe = escape(message) if message else ""
# every console.print branch now uses safe instead of message
```

Prefix literals (`"● "`, `"→ "`) are constants and not escaped. `logger` calls keep the unescaped form — `AnsiStrippingFilter` (`demetra/services/utils.py:19-22`) doesn't interpret markup.

### Fix 2 — Increment only on failure (`demetra/services/watcher.py:27-88`)

- Pre-check now reads `session.run_attempts > MAX_RUN_ATTEMPTS` without incrementing.
- `increment_run_attempts` moved after the failure paths (`returncode != 0`, `TimeoutError`, `RuntimeError/OSError`), with a post-increment cap check on the same call.
- `AutoCancelledError`/`UserCancelledError` (`main.py:91-100`) return 0 and never increment.

## Test Results

- `test_run_workflow_skips_when_max_attempts_reached` — pre-check bails, `assert_not_called()` on increment.
- `test_run_workflow_proceeds_when_below_max` — success, no increment.
- `test_run_workflow_increments_on_nonzero_exit` / `_on_timeout` / `_bails_after_increment_exceeds_limit` — failure paths.
- `test_print_message_escapes_rich_markup[heading|result|info|error|None]` — parametrised, asserts escaped form reaches `console.print`.

**500 passed.** `ruff`, `ty`, `bandit`, `pre-commit` clean.

## Source — [[2026-02-14-add-tui-support]]

Rich-based CLI TUI via `demetra/services/tui.py:print_message` as single output path, replacing `print()`. `main.py` plan→build→review loop with `--auto` / `--project-name` flags.

## Known follow-up (not fixed here)

In `manti-by/odin` repo, not `demetra`:
- `odin/tests/views/test_index.py` `test_*_returns_*_when_build_missing` assumes `frontend/dist/` absent but PWA build creates it — extend `FRONTEND_DIST_DIR` override pattern.
- Review feedback (precache prefix vs `base: "/static/"`, missing `denylist` on `NavigationRoute`, `__WB_MANIFEST` typing) never applied — build loop re-staged same diff.
- Runtime `MAX_RUN_ATTEMPTS` was 3 vs default 5 — surface effective value in watcher startup log.

> **Consistency note (2026-08-24):** `demetra/services/tui.py` → `demetra/services/runtime/tui.py`; `demetra/services/utils.py` → `demetra/services/runtime/utils.py`.

> **Status update (2026-08-27):** `demetra/services/watcher.py` → `demetra/services/daemons/watcher.py` (commit `04436c6`). Behavior unchanged: `increment_run_attempts` only after failure, pre-check on `session.run_attempts`, cap is `5` (see [[2026-06-08-max-run-attempts-for-a-ticket]]).

## Source — [[2026-06-08-max-run-attempts-for-a-ticket]]

`run_attempts` + `MAX_RUN_ATTEMPTS` (5) guards infinite runs; incremented only on failure → Awaiting Input. Originally decided 2026-06-08.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: none
- External: [MNT-136](https://linear.app/mnt/issue/MNT-136) · Session log: `/var/log/demetra/sessions/4c32355e-55bf-478f-8cd6-832bacafe6f9.log` · Watcher log: `/var/log/demetra/demetra.log:390177`
