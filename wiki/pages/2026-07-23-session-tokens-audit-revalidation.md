---
title:              Session Tokens Audit Revalidation — cumulative counter vs context threshold
date:               2026-07-23
type:               investigation
status:             resolved
session_id:         3eae8036-e679-4a09-be65-144e738741e0
services:           [opencode, database, workflows, groq]
branch:             -
tickets:            [MNT-145]
tags:               [session-history, compaction, tokens, opencode-export, audit]
related:            [2026-07-16-session-history-tokens-null.md]
---

# Session Tokens Audit Revalidation — cumulative counter vs context threshold

## TL;DR

Revalidated every claim in `wiki/audits/2026-07-23-session-tokens/RESULT.md` against the working tree, git
history, and the Odin DB (`192.168.1.100:5432`). All 192-row statistics reproduced
exactly, but two causal claims were refuted: the NULL-length rows were caused by the
already-fixed pipe truncation (not cleanup ordering), and "compaction never fires" is
wrong — it was live for most of the sample and fired constantly because `length` is a
**cumulative** session counter compared against a **context-size** threshold. The audit
was rewritten in place and an implementation plan for a Sonnet-class agent was written
to `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md`.

---

## Net effect

The compaction feature (MNT-122, disabled by MNT-145) cannot work as designed: its
threshold input can only grow, so it triggers on every build iteration after the first
few messages. The fix is a metric change (current context from the last assistant
message of `opencode export`), not re-enabling the existing code. Two of the original
audit's recommendations were dropped as refuted, one as useless; the corrected audit and
a hard-constraints build plan are in the repo root.

## DB revalidation (Odin, 192.168.1.100:5432)

Re-ran the full query battery: totals (192 rows / 18 sessions, sum length
1,945,130,043), medians, per-step distribution, threshold breaches (143/128/73/3), the
four all-NULL sessions, shrink events (0), and daily volume. Every figure in the
original audit reproduced exactly (build avg is 16.8 M; the audit had rounded to
16.7 M).

## `length` is cumulative — the audit's central blind spot

**File:** `demetra/library/models.py:53` — `TokenUsage.total` sums
`input + output + reasoning + cache_read + cache_write` from session-level
`info.tokens` of `opencode export`.

Build rows reach 40 M tokens — no model context is that large, so these are running
totals for the whole session (confirmed by the 8.2 M single-reading measured in
[[2026-07-16-session-history-tokens-null]]). Consequences:

- The "0 shrink events ⇒ compaction never ran" query is invalid — a cumulative counter
  cannot decrease even when `/compact` succeeds.
- Comparing it to `CONTEXT_COMPACTION_THRESHOLD` (100k, `demetra/settings.py:40`) means
  ~74% of rows are permanently "over threshold"; `/compact` fired on virtually every
  build iteration while enabled.
- Excluding cache reads doesn't help — `input + output + reasoning` is also monotonic.

## Compaction timeline (git history)

- `efbf4c7` (2026-07-06) — MNT-122 adds `check_and_compact_context`.
- `5f8e428` (2026-07-21 14:12 +03) — "MNT-145: Disable context compaction" comments out
  the only caller (**File:** `demetra/workflows/build.py:77`).

So compaction was *live* for most of the sampled period (07-16 → 07-21), contradicting
the audit's "never actually fires". The constant firing is the likely motivation for
MNT-145.

## NULL rows: ordering claim refuted, truncation timeline confirmed

The audit claimed rows go NULL because recording runs after `git_cleanup` removed the
worktree. False in every committed version: the `failed` row is written at
`demetra/workflows/cleanup.py:95`, `git_cleanup` at `cleanup.py:103`; the `completed`
row is written in `commit_and_push` (`cleanup.py:69`), before `cleanup_workflow` runs.

The DB timeline instead matches the pipe-truncation fix from
[[2026-07-16-session-history-tokens-null]] exactly: all 48 NULL rows are timestamped
before `f96b07f` ("Fix session tokens countes", 2026-07-17 00:08 +03) — 44 on 07-16,
the last 4 at 00:01–00:02 on 07-17 — and there are **zero** NULLs in the 144 rows
since. Solved problem; no action needed.

## Smaller corrections

- `extract_plan` is at `demetra/services/groq.py:101`, not `:90` (`:90` is inside
  `process_text_with_groq`); the truncate-before-Groq recommendation itself stands.
- `record_session_step_history` is at `demetra/services/database.py:942` in the working
  tree (the audit's `:929` matched HEAD; an uncommitted `get_session_id_by_task_id` was
  added above it).
- `cache_write_tokens = 0` in all 192 rows **and** in the live payload measured on Odin
  on 07-16 — likely genuine opencode behaviour for these models, not a parser bug.
- The proposed 10 s TTL cache on the export has limited benefit (one export per build iteration,
  minutes apart, so a cache would rarely hit) and the `length = -1` sentinel for NULL sessions would skew aggregates
  that currently ignore NULLs correctly.

## Open questions

- Does `opencode export` expose per-message token usage (needed for the current-context
  metric)? Blocking prerequisite — Step 1 of the build plan verifies the real schema.
- Is `cache.write` ever non-zero for the opencode-go models in use?
- Could not verify whether the four all-NULL sessions are recoverable: SSH to Odin was
  denied (publickey), and their worktrees are gone.

---

## Follow-ups

- Execute `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md` (repo root): context metric from last
  assistant message, re-enable `build.py:77`, `model` + `context_tokens` columns,
  Groq input cap.

## References

- Related: [[2026-07-16-session-history-tokens-null]]
- Root docs: `wiki/audits/2026-07-23-session-tokens/RESULT.md` (corrected audit), `wiki/audits/2026-07-23-session-tokens/BUILD_PLAN.md` (implementation plan)
