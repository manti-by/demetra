---
title: Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications
date: 2026-09-14
type: debug
status: open
session_id: ses_f5e6bd69bffexNX7o87koO5QLl
services: [listener, daemons, runtime, github]
branch: "-"
tickets: []
tags: [listener, github, notifications, asyncio, readline, limit, gh, merge, rebase]
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

## Follow-ups

- Fix applied, listener restarted, then watch `/var/log/demetra/listener.log` for a first `Processing notification` / `Enqueuing` line.

## References

- Related: [[2026-07-16-fix-notification-mark-read]]
- External: `demetra/listener.py`, `demetra/services/daemons/listener.py`, `demetra/services/runtime/utils.py`, `demetra/services/runtime/subprocess.py`