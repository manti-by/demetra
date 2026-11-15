---
title: Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications
date: 2026-09-14
type: debug
status: resolved
session_id: ses_f5e6bd69bffexNX7o87koO5QLl
services: [listener, daemons, runtime, github]
branch: "-"
tickets: []
tags: [listener, github, notifications, asyncio, readline, limit, gh, merge, rebase, infinite-loop, listener-attempts]
related: [2026-07-16-fix-notification-mark-read.md]
---

# Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications

## TL;DR

The GitHub notification listener (`demetra/listener.py`) has never processed a single notification: the log shows 2792 `Error polling GitHub notifications` tracebacks and **zero** `Processing notification` / `Enqueuing` lines. Every poll aborts in `live_stream` with `ValueError: Separator is not found, and chunk exceed the limit` — the `asyncio.StreamReader.readline()` 64KB limit is hit because `gh api /notifications --jq .` emits the whole notification array as one compact JSON line, and the unread backlog pushes it past 64KB. Because the crash happens before notifications are inspected or marked read, the backlog persists and the listener fails every ~60s poll forever. Diagnosis only; fix not applied this session.

---

## Symptom

`/var/log/demetra/listener.log` (78179 lines) is dominated by a repeating error, once per `LISTENER_POLL_INTERVAL` (60s):

```
ValueError: Separator is not found, and chunk exceed the limit
2026-09-14 20:16:52 ERROR : Error polling GitHub notifications
```

Counts across the whole log:

- **2792** × `Error polling GitHub notifications`
- **0** × `Processing notification`
- **0** × `Enqueuing` (merge / rebase / fix review findings)

So merge, rebase and `@demetra-ai fix review findings` comments are never picked up. The intermittent `No notifications found` lines appear only when GitHub auto-snoozes old threads and the payload temporarily dips under the 64KB line limit.

## Step 1 — Trace the exception

The full traceback pins the failure:

- `demetra/listener.py:37` — `notifications = await get_notifications()` in the poll loop
- `demetra/services/daemons/listener.py:36` — `run_command(command=[gh, api, -H, "Accept: application/vnd.github+json", /notifications, --jq, .], ...)`
- `demetra/services/runtime/subprocess.py:152` — `await asyncio.gather(*streams)`
- `demetra/services/runtime/utils.py:87` — `if not (line := await stream.readline())` in `live_stream`
- `asyncio/streams.py:663` — `raise exceptions.LimitOverrunError('Separator is not found, and chunk exceed the limit', offset)`

The exception escapes `run_command` → `get_notifications` → is caught at `listener.py:85` (`except Exception: logger.exception(...)`), aborting that poll iteration before any notification is inspected.

## Step 2 — Understand the readline limit

`asyncio.StreamReader.readline()` enforces a hard `_DEFAULT_LIMIT = 2**16` (64KB): if no `\n` separator is found within 64KB of buffered data it raises `LimitOverrunError`, which `readline()` re-raises as the `ValueError` seen in the logs.

The `gh api /notifications --jq .` command emits the entire notifications JSON array as **one compact line** (gh's `--jq` writer encodes each jq result with `json.Encoder.Encode`, no indentation, and `.` yields the whole array as a single value). Once the unread-inbox backlog makes that one line exceed 64KB, `readline()` fails.

## Step 3 — Evidence this is the whole story

- The failure starts at the first lines of the log and never recovers; no notification has ever been processed.
- The crash occurs **before** `mark_notification_read` (demetra/listener.py:74) can run, so the offending threads stay unread → same oversized payload → same failure every poll. Self-sustaining.
- `fetch_subject_body` (demetra/services/daemons/listener.py:98-125) fetches a single comment `.body` the same way — a large comment body would hit the identical limit even if the notifications list were readable.

## Root cause

`live_stream` (`demetra/services/runtime/utils.py:87`) reads subprocess stdout with `asyncio.StreamReader.readline()`, which has a built-in 64KB per-line limit. The listener's `gh api /notifications --jq .` stdout is a single JSON line that exceeds 64KB whenever enough unread notification threads accumulate, raising `ValueError: Separator is not found, and chunk exceed the limit`. This aborts `get_notifications()` on every poll, so the listener never inspects notifications, never fetches comment bodies, and never enqueues merge / rebase / fix-review-findings workflows. The failure is permanent because the crash prevents the notifications from being marked read.

## Resolution / Fix

Not applied this session (diagnosis only). Proposed fix, matching the existing pattern:

- **`get_notifications` and `fetch_subject_body`:** switch from `run_command` to `run_command_to_file` (`demetra/services/runtime/subprocess.py:164`), which redirects stdout to a temp file and reads it back after the process exits — no pipe / readline limit. Already used for the same "output exceeds the 64KB pipe/readline buffer" reason at `demetra/services/agents/opencode.py:451`.
- **Alternative hardening:** make `live_stream` read in chunks and split on newlines instead of `readline()`, removing the 64KB ceiling for every caller of `run_command` (riskier, broader blast radius).

## Known follow-up (not fixed this session)

- Apply the `run_command_to_file` fix to `get_notifications` (and ideally `fetch_subject_body`).
- Secondary observation: `gh auth status` on this host reports the `demetra-ai` token invalid; worth verifying the container/deployed token is the one in use and healthy after the readline fix.
- Consider `--jq '. [0:100]'` or per-thread pagination as a cheaper mitigation if the backlog stays large.

---

## Source — [[2026-07-16-fix-notification-mark-read]]

Listener loop-protection decisions (2026-07-16): `mark_notification_read` is gated on success — `process_merge/rebase_notification` returning `False` (no session, no `project_id`, unknown action) leaves the notification unread for retry — and a per-session attempts counter breaks the loop after N failures (`MAX_ATTEMPTS["listener"]` = 5, `demetra/settings.py`; helpers `increment_listener_attempts`/`reset_listener_attempts` in `demetra/services/persistence/database.py:1028`/`:999`). Originally decided in [[2026-07-16-fix-notification-mark-read]] on 2026-07-16.

## Follow-ups

- ~~Fix applied, listener restarted~~ **Fix NOT yet applied** (re-confirmed 2026-10-08: still `run_command` at `demetra/services/daemons/listener.py:36,121`, `stream.readline()` at `demetra/services/runtime/utils.py:96,117`) — apply the `run_command_to_file` switch above, restart the listener, then watch `/var/log/demetra/listener.log` for a first `Processing notification` / `Enqueuing` line.

> **Consistency note (2026-10-26, Consistency Agent):** re-verified on HEAD `be55753` — `get_notifications` and `fetch_subject_body` still use `run_command` (`demetra/services/daemons/listener.py:36,121`) and `live_stream`/`log_stream` still call `stream.readline()` (`demetra/services/runtime/utils.py:96,117`). No fix has landed; status stays `open`.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

> **Resolved (2026-11-15):** Fix applied. `get_notifications` and `fetch_subject_body` now use `run_command_to_file` (`demetra/services/daemons/listener.py`), keeping `run_command` only for `mark_notification_read` (tiny PATCH response). Reproduced the failure mode with a 100-element compact JSON payload: `run_command` raises `ValueError: Separator is found, but chunk is longer than limit` while `run_command_to_file` returns the full 102KB payload parsed. Live evidence at fix time: `gh api /notifications --jq .` emits **117,287 bytes on one line** (26 unread threads, backlog intact because crashes prevented mark-read), `gh auth status` healthy for `demetra-ai`. Tests updated in `tests/test_listener.py` (7 patch targets renamed); 53 pass, ruff/ty clean. Requires image rebuild + listener container recreate (`make deploy`) to take effect.

## References

- Related: [[2026-07-16-fix-notification-mark-read]]
- External: `demetra/listener.py`, `demetra/services/daemons/listener.py`, `demetra/services/runtime/utils.py`, `demetra/services/runtime/subprocess.py`