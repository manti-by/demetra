---
title: Rich MarkupError kills workflow subprocess and run_attempts counter overcounts
date: 2026-07-21
type: debug
status: resolved
session_id: -
services: [watcher, tui, main]
branch: -
tickets: [MNT-136, MNT-17]
tags: [rich, markup, tui, watcher, run-attempts, error-handling, agents, cli, textual, investigation]
related: [2026-02-14-add-tui-support.md]
---

# Rich MarkupError kills workflow subprocess and run_attempts counter overcounts

## TL;DR

MNT-136 ("PWA & static asset migration") surfaced as `Max run attempts reached` after three
identical workflow crashes. The crash was a `rich.errors.MarkupError` raised inside
`demetra.services.tui.print_message` when a review-agent finding contained a regex-style
denylist (`[/^\/admin/, ...]`) that Rich mis-parsed as a closing tag. The exception
propagated out of the subprocess, which then exited non-zero — and every non-zero exit
counted against `run_attempts`, so a single real failure mode was indistinguishable from
N different ones. Two surgical fixes: escape Rich markup in `print_message`, and only
increment `run_attempts` after the subprocess fails (not before every run).

## Symptom

- Linear ticket MNT-136 in `Awaiting Input` with comment "Max run attempts reached".
- DB row `sessions.run_attempts = 4`, `step = "failed"` (task_id `4c32355e-55bf-478f-8cd6-832bacafe6f9`).
- Watcher log `demetra.log:390177`:
  `WARNING: Max run attempts (3) reached for task 4c32355e-… , moving to Awaiting Input`
- Every prior workflow run in the same session log ends with
  `ERROR : Workflow failed for task 4c32355e-… : ` (empty stderr) followed by
  `Moving back a ticket in TODO column` — i.e. the subprocess exited non-zero with no
  captured error text.

The session log for a sibling task in the same run (MNT-138, file
`89703bca-5da6-4715-8a87-704724f8d74d.log`) actually completed successfully (PR #22) — so
the failure was specific to MNT-136's review findings, not the watcher / queue.

## Step 1 — the immediate crash is a Rich parsing error, not a build failure

The first workflow subprocess crash (`demetra.log:353928`) sits one line above
`MarkupError`:

```
File ".../rich/markup.py", line 161, in render
    raise MarkupError(
        f"closing tag '{tag.markup}' at position {position} doesn't match any open tag"
    )
rich.errors.MarkupError: closing tag '[/^\/admin/, /^\/api/]' at position 476 doesn't match any open tag
```

The same exception fires a second time (`demetra.log:390169`):

```
rich.errors.MarkupError: closing tag '[/^\/admin/, /^\/api/, /^\/static/, /^\/media/]' at position 328
```

Both have empty `Workflow failed … :` lines in the watcher because the Python traceback
is raised during `console.print(...)` *after* `process.communicate()` has consumed the
subprocess stderr — so `stderr.decode()` is `b""` by the time the watcher reads it.

## Step 2 — where the malformed string comes from

The text Rich is choking on is the literal output of a review agent, surfaced via
`demetra.workflows.review.run_review_agents` and printed by
`demetra.services.tui.print_message`:

- **`File:** demetra/workflows/review.py:43-44`
  ```python
  findings_text = "\n".join(f"{i + 1}. {finding}" for i, finding in enumerate(meaningful))
  print_message(findings_text, style="result")
  ```
- The review finding itself (last review pass on MNT-136, `4c32355e-…log:27093-27095`):
  > `frontend/src/sw.ts:19` — `new NavigationRoute(createHandlerBoundToURL("/static/index.html"))`
  > matches every navigation inside the root scope, so direct visits to `/admin/`, `/api/`,
  > `/static/`, and `/media/` will be served the SPA shell instead of hitting Django. Pass a
  > `denylist` as the second argument, e.g. `{ denylist: [/^\/admin/, /^\/api/, /^\/static/, /^\/media/] }`.

- **`File:** demetra/services/tui.py:16-33` (pre-fix)
  Every branch passed the raw `message` straight to `console.print(message, style=…)`.
  Rich's `console.print` interprets `[…]` as markup, so `[/^\/admin/, …]` is parsed as a
  *closing tag* (it starts with `[/`), the tag stack underflows, and the exception fires
  from the same line of Rich's `markup.py` that the log cites.

Confirmed by reproducing in isolation: `rich.markup.escape('[/^\\/admin/]')` returns
`'\\[/^\\/admin/]'` — i.e. only the `[` is escaped, but that's enough to neutralise Rich's
parser.

## Step 3 — why three "different" workflow runs all hit the same crash

The watcher's `run_workflow` had two independent problems that compounded:

1. **`File:** demetra/services/watcher.py:32 (pre-fix)
   ```python
   attempts = await increment_run_attempts(task_id)
   if session and attempts > MAX_RUN_ATTEMPTS:
       ...move to Awaiting Input, return False
   ```
   Increment-then-check means every watcher call (success, auto-cancel, *or* failure)
   burns an attempt slot. The session's first run was an `AutoCancelledError` (the
   plan-agent emitted 5 open questions, `plan.py:119-129` posted them to Linear and
   moved the ticket to `awaiting_input`); the user moved the ticket back to `todo`; the
   watcher re-triggered. That clean run still counted as attempt 1.

2. **Same line, also pre-fix:** the post-failure `return False` path did not re-check
   the cap, so the `Max run attempts reached` message was *only* logged on the bail-out
   watch call — every other failure looked indistinguishable from a normal retry. That
   is why the symptom ("Max run attempts") appeared without a clean chain of "Workflow
   failed" messages tying it back to the same exception.

With `MAX_RUN_ATTEMPTS=3` (overridden in the running process — see `settings.py:37`
default of 5) and 1 auto-cancel + 2 MarkupError runs, the 4th watcher call
(`attempts=4 > 3`) is the one that bails. The DB shows `run_attempts=4` because all
four watcher calls incremented, even though only two of them were actual failures.

## Root cause

Two bugs in series:

- **`print_message` does not escape Rich markup.** Any user / agent / review output
  containing `[…]` is interpreted as Rich tag syntax; the only way to crash the
  subprocess from a single printed string is to hand Rich an unbalanced tag. The
  review agent's regex suggestions reliably produce this.
- **`run_attempts` is incremented unconditionally before the workflow runs.** The
  counter conflates "watcher triggered" with "workflow failed", so the
  `MAX_RUN_ATTEMPTS` cap does not mean "3 failed runs" — it means "3 watcher calls,
  regardless of outcome", which prematurely exhausts the budget on legitimate
  auto-cancellation paths.

## Resolution / Fix

### Fix 1 — escape Rich markup in `print_message`

**File:** demetra/services/tui.py:4, 17-35
```diff
+from rich.markup import escape
 ...
 def print_message(message: str, style: str | None = None):
+    safe = escape(message) if message else ""
     if style == "heading":
         console.print("\n\u25cf ", style="bold bright_green", end="")
-        console.print(message, style="bold bright_white")
+        console.print(safe, style="bold bright_white")
     elif style == "result":
         console.print("→ ", style="bold bright_green", end="")
-        console.print(message, style="white")
+        console.print(safe, style="white")
     elif style == "info":
         console.print()
-        console.print(message, style="bright_black")
+        console.print(safe, style="bright_black")
     elif style == "error":
         console.print()
-        console.print(message, style="red")
+        console.print(safe, style="red")
         ...
     else:
-        console.print(message)
+        console.print(safe)
```

The literal prefix strings (`"\n● "`, `"→ "`) are constants and don't need escaping —
only user/agent-supplied messages do. The `logger.info(message)` / `logger.error(message)`
calls deliberately keep the *un*escaped message because the file handler's
`AnsiStrippingFilter` (`demetra/services/utils.py:19-22`) doesn't interpret markup.

### Fix 2 — increment `run_attempts` only on actual failure

**File:** demetra/services/watcher.py:27-88
```diff
 async def run_workflow(project_name: str, task_id: str) -> bool:
     if not task_id:
         logger.error(f"Task ID is empty: {task_id}")
         return False

-    attempts = await increment_run_attempts(task_id)
     session = await get_session(task_id)
-    if session and attempts > MAX_RUN_ATTEMPTS:
+    if session and session.run_attempts > MAX_RUN_ATTEMPTS:
         logger.warning(f"Max run attempts ({MAX_RUN_ATTEMPTS}) reached for task {task_id}, moving to Awaiting Input")
         await post_comment(task_id=task_id, body="Max run attempts reached")
         await update_ticket_status(task_id=task_id, state_id=LINEAR["states"]["awaiting_input"])
         return False

     process = None
     try:
         ...
         if process.returncode == 0:
             logger.info(f"Workflow completed successfully for task: {task_id}")
             return True

         logger.error(f"Workflow failed for task {task_id}: {stderr.decode()}")
     except TimeoutError:
         ...
     except (RuntimeError, OSError) as e:
         ...

+    attempts = await increment_run_attempts(task_id)
+    if attempts > MAX_RUN_ATTEMPTS:
+        logger.warning(f"Max run attempts ({MAX_RUN_ATTEMPTS}) reached for task {task_id}, moving to Awaiting Input")
+        await post_comment(task_id=task_id, body="Max run attempts reached")
+        await update_ticket_status(task_id=task_id, state_id=LINEAR["states"]["awaiting_input"])
+        return False
+
     return False
```

Net effect: `run_attempts` now counts failed workflow runs only. Auto-cancel and
user-cancel exits (`AutoCancelledError` / `UserCancelledError` in `main.py:91-100`)
leave it untouched because the subprocess returns 0 in both cases and we `return True`
before the new increment block. The cap check still happens on every watcher call
(via the new pre-check on `session.run_attempts`), and the bail-out path is now
reachable on the *same* watcher call that produced the failure.

## Test Results

Updated `tests/test_more_coverage.py::TestWatcherService` and
`tests/test_api_coverage.py::TestTuiService` to match the new behaviour:

- `test_run_workflow_skips_when_max_attempts_reached` — pre-check bails, asserts
  `mock_increment_run_attempts.assert_not_called()`.
- `test_run_workflow_proceeds_when_below_max` — successful run, asserts no increment.
- `test_run_workflow_increments_on_nonzero_exit` — non-zero exit increments once, no bail.
- `test_run_workflow_bails_after_increment_exceeds_limit` — increment to 4 > 3 → bail
  with `post_comment` + `update_ticket_status` asserted.
- `test_run_workflow_increments_on_timeout` — `TimeoutError` increments once and kills the process.
- `test_print_message_escapes_rich_markup[heading|result|info|error|None]` —
  parametrised, feeds the MNT-136 review text into `print_message` and asserts the
  Rich-escaped form is what reaches `console.print`.

Full suite: **500 passed**. `ruff check`, `ruff format --check`, `ty check`,
`bandit -c pyproject.toml`, and `pre-commit run` all pass on the touched files.

## Source — [[2026-02-14-add-tui-support]]

Originally decided in [[2026-02-14-add-tui-support]] on 2026-02-14 (MNT-17): the
CLI TUI is **Rich-based, not a full TUI library**. A `print_message` service in
`demetra/services/tui.py` is the single output path for all workflow output and
replaces bare `print()` calls. `main.py` is an interactive plan → build → review
loop with argparse flags `--auto` (headless, later extended by MNT-30/MNT-34) and
`--project-name <name>`, rendered through Rich formatters and status widgets. MNT-17
originally started as an investigation of TUI frameworks; Rich was chosen because it
is Python-native with no heavy runtime dependency.

## Known follow-up (not fixed this session)

These were diagnosed but live in the `odin` repo, not `demetra`, so the right fix is a
follow-up PR against `manti-by/odin`:

- **`odin/tests/views/test_index.py`** — the new
  `test_*_returns_*_when_build_missing` tests assume `frontend/dist/` does not exist,
  but the PWA build (`vite build` + `vite-plugin-pwa`) creates it, so they always
  return 200 where the test expects 500/503. Build agent noted this correctly
  (`4c32355e-…log:3069`) but never patched the test isolation. Other tests in the same
  file already use `settings.FRONTEND_DIST_DIR` overrides — extend that pattern.
- The review feedback on the MNT-136 implementation itself is sound (precache URL
  prefix vs. `base: "/static/"`, missing `denylist` on the `NavigationRoute`,
  `ServiceWorkerGlobalScope.__WB_MANIFEST` typing) but was never applied; the build
  loop just kept retrying past the same review comments. The plan-build contract should
  be tightened so the build agent must converge on the review findings, not merely
  re-stage the same diff.
- The actual `MAX_RUN_ATTEMPTS` runtime value was 3 (`demetra.log:390177`); the
  `settings.py:37` default is 5 and the `.env` does not set it. The mismatch was
  inherited from a previous override and is not visible from the current config.
  Consider surfacing the effective value in the watcher startup log.

## References

- Related: none
- External:
  [MNT-136 — PWA & static asset migration (Linear)](https://linear.app/mnt/issue/MNT-136)
  · Session log: `/var/log/demetra/sessions/4c32355e-55bf-478f-8cd6-832bacafe6f9.log`
  · Watcher log: `/var/log/demetra/demetra.log:390177`
