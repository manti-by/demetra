---
title: MNT-251 — Rebuild agent session attribution and token accounting for opencode v2
date: 2026-10-16
type: implementation
status: resolved
session_id: ses_ebb87d8cfffePjoAvLThMh0EBJ
services: [agents, persistence, workflows, api, library, vcs, react]
branch: opencode/feature/mnt-251-agent-session-attribution
tickets: [MNT-251, MNT-246, MNT-241, MNT-245, MNT-234, MNT-228, MNT-181, MNT-122, MNT-151]
tags: [opencode, cli-v2, tokens, sessions, accounting, compaction, session-history, migrations, agent-attribution]
related: [2026-10-16-opencode-v2-session-token-accounting.md, 2026-07-07-add-context-compaction.md, 2026-07-16-session-history-tokens-null.md, 2026-08-19-build-agent-stale-session-deleted-worktree.md, 2026-07-23-session-tokens-audit-revalidation.md, 2026-09-30-mnt-228-intermediate-history-states.md, 2026-08-25-mnt-181-total-tokens-counter.md, 2026-07-23-session-history-modal.md]
---

# MNT-251 — Rebuild agent session attribution and token accounting for opencode v2

## TL;DR

Implemented the full MNT-251 build plan in one branch: Phase 1 makes the opencode CLI layer version-aware (`run` no longer passes `--dir`; `session export` on v2 / `export` on 1.x; export stays file-backed), fixes the compaction no-op (`run --command compact` on 1.x, deliberately unsupported on v2 where the flag is gone, with the fork-once build session documented as the only context bound and a test that asserts the measured context actually shrank), persists `info.agent` / serialized `info.model` / `info.cost` / `info.outcome`, adds a one-per-process startup smoke test, and surfaces readable errors from both default and NDJSON streams. Phase 2 adds an `agent_sessions` cursor table plus `session_history.task_id`/`agent_session_id`/`kind`/`cost`/`agent`, migrates and backfills legacy rows, records one exact-delta invocation row per `(session, step)`, forks the build session exactly once, resolves history by `task_id` after worktree deletion, and re-points the API totals at `kind='invocation'`. 1020 Python tests + 107 frontend tests pass; `ruff`/`ty`/`bandit` clean.

---

## Overview

The spike page [[2026-10-16-opencode-v2-session-token-accounting]] is the v2 ground truth this build follows; this page records the implementation. Two problems were fixed together because repairing the export path without the delta model just restores MNT-246's 6.4× over-report, and migrating to v2 without the delta model bakes it in.

- **Phase 1 (independently shippable):** v2 CLI compatibility + the compaction no-op that has never worked on either version.
- **Phase 2 (data model):** per-invocation sessions and exact token deltas, migrations, API/UI, tests.

Go/no-go decisions resolved explicitly (the ticket demanded "do not ship a third silent no-op"):

- **`--format json` for `run`: not adopted.** `run` keeps the default output format; the wrapper still defensively parses NDJSON `type=="error"` on stdout so a future switch cannot leak a raw blob.
- **Compaction on v2: deliberately removed, not silently no-op'd.** v2's `run` has no `--command` flag, so `opencode_compact_session` returns a non-zero exit with an explanatory message and `check_and_compact_context` skips it via `opencode_supports_compaction`, logging that the fork-once build session bounds context.
- **Fork cursor: never seeded from the parent** (settled by the spike measurement — a fork's `info.tokens` restarts).
- **Stale pointer: option (b).** History resolves through `agent_sessions`/`session_history` by `task_id`; `sessions.session_id` becomes display-only.

---

## Step 1 — opencode CLI is version-aware

**File:** `demetra/services/agents/opencode.py`

`--dir` was dropped from every `run` invocation — `run_command` already sets `cwd=target_path`, so the flag was redundant on 1.x and rejected by v2. Export is version-aware via a cached `opencode --version` major parse:

```python
def _export_command(major: int, session_id: str) -> list[str]:
    if major >= OPENCODE_V2_MAJOR:
        return [str(OPENCODE["path"]), "session", "export", session_id]
    return [str(OPENCODE["path"]), "export", session_id]
```

- `get_opencode_major_version` caches the parsed major per CLI path; when the version is unknown, `get_opencode_session_export` tries the v2 form then the v1 form so a failed probe cannot silently disable accounting.
- Export stays **file-backed** (`run_command_to_file`): `session export` through a pipe truncates at a 64 KB multiple and yields invalid JSON ([[2026-07-16-session-history-tokens-null]]).
- `opencode_supports_compaction` returns `major is None or major < 2`.
- `opencode_compact_session` returns `(1, "", "compaction is not supported by this opencode version (no 'run --command')")` on v2 and `run --session <id> --command compact` on 1.x.

## Step 2 — Compaction actually shrinks the context, or is reported

**File:** `demetra/workflows/build.py::check_and_compact_context(context, context_tokens)`

The gauge is now passed in (the build invocation's `context_tokens` snapshot) rather than re-derived from the cumulative `length`, so the threshold compares against context size, not a running total. After compaction the session is re-exported and the measured context is compared to the pre-compaction gauge:

```python
if usage.context >= context_tokens:
    print_message(
        f"Compaction did not reduce context ({usage.context:,} tokens, was {context_tokens:,}); "
        "the fork-once build session remains the only context bound.",
        style="warning",
    )
```

Unsupported versions skip compaction with a warning naming the fork-once design as the bound — never a silent full-context turn. This closes the three-month gap where `2026-07-07-add-context-compaction` recorded compaction as "live" while its tests only asserted the subprocess was called.

## Step 3 — Attribution and a startup smoke test

- `_build_session_export` reads `info.agent`, serializes `info.model` (`{providerID, id, variant}` → `provider/model#variant`), and reads `info.cost` / `info.outcome`.
- `_message_role_and_tokens` handles both shapes (`msg["info"]["role"]` on 1.x, `msg["type"]` on 2.x), so `context_tokens` populates on v2 where the old `isinstance(msg_info, dict)` guard failed for every message.
- `format_agent_error` returns a readable message from stderr, or the `error.message` of an NDJSON `type=="error"` event on stdout, or a clear "exited with code N without output" — never a raw blob or "unknown error".
- `verify_opencode_cli` runs once per process at startup: logs `opencode --version`, asserts `run --help` accepts `--model/--agent/--session/--fork/--title`, and that the version-appropriate `export` subcommand exists. Wired into `main.py`.

## Step 4 — Data model: `agent_sessions` + invocation rows

**Files:** `migrations/versions/c8d9e0f1a2b3_create_agent_sessions_table.py`, `d9e0f1a2b3c4_alter_session_history_agent_columns.py`

`agent_sessions` is one row per `(task_id, session_id)` holding the cumulative cursor, attribution, `fork_of` lineage, `is_primary`, and a partial unique index `uq_agent_sessions_primary` on `task_id WHERE is_primary`. `session_history` gains `task_id`, `agent_session_id` (FK → `agent_sessions.id`, `ON DELETE CASCADE` — the FK target MNT-246 had wrong), `kind`, `cost`, `agent`; `session_id` is relaxed to nullable (research never had one).

Backfill preserves every legacy total:

- `kind` defaults to `'step'`, then is set to `'invocation'` where any token column is non-NULL, so populated `plan`/`build`/`completed`/`failed` rows stay in totals while empty markers stay `'step'`.
- `task_id` is backfilled from the `sessions` join on `session_id`.

`record_agent_invocation` computes `delta[f] = max(0, info.tokens[f] - cursor[f])`, advances the cursor, and upserts one `kind='invocation'` row per `(task_id, session_id, step)`. The previous primary is demoted **before** the insert/update because the partial unique index rejects a second primary row (a real bug found by the tests). A `None` usage records attribution without advancing the cursor.

## Step 5 — One row per invocation across every workflow

- Build forks the plan session exactly once (`fork = is_first_build and context.session_id is not None`); later iterations resume the fork without `--fork`, and the fork's first delta equals its own `info.tokens`.
- Research/resolve/merge/rebase/review_fixes each create their own session resolved by unique title and record an invocation row (`review_fixes.py`, `services/vcs/merge.py`, `services/vcs/rebase.py`, `workflows/merge.py`, `workflows/rebase.py`).
- Review records one row per `(round, model)` via unique titles.
- Step rows use `record_session_step(task_id, step)` (no `session_id`), so `awaiting_input` produces exactly one row; `update_session_step` only advances `sessions.step`.
- `cleanup_workflow` calls `invalidate_agent_sessions(task_id)` after worktree removal (persistence stays out of `services/vcs/git.py`, per layering).

## Step 6 — API / UI resolve by `task_id`

- `GET /{task_id}/history` resolves through `get_session_history(task_id)` (ordered by `created_at, id`) and `_compute_total_tokens` sums only `kind='invocation'` rows, dropping the `row.length` fallback.
- `get_pending_session_task_ids` uses `NOT EXISTS (agent_sessions)` instead of `session_id == ""`, so plan-only/research-only tasks are no longer pending forever.
- `delete_session` deletes both `session_history` (all kinds) and `agent_sessions`, leaving no orphans.
- React `SessionHistory.tsx` / `SessionArtifacts.tsx` drive tokens/attribution from the explicit `kind` field instead of null-sniffing, and `hasHistory` is widened.

---

## Test Results

- `uv run pytest tests/` — **1020 passed**.
- `npx vitest run` — **107 passed** (10 files); `npx tsc --noEmit` clean.
- `uv run ruff check .` / `uv run ruff format --check .` / `uv run ty check` clean.
- `uv run bandit -c pyproject.toml -r demetra main.py` — 0 issues.
- Migrations verified on a scratch DB (`demetra_mnt251`, created then dropped): full `alembic upgrade head` clean, `downgrade -1`/re-upgrade works, and the legacy backfill proven (a token row → `kind='invocation'` with `task_id` backfilled; an empty row → `kind='step'`).

Named tests requested by the ticket:

- `TestAgentSessions` — cursor advance, one row per resumed session, fork lineage without cursor seeding, single primary per task, failed export does not advance the cursor.
- `TestSessionHistoryKind` — step and invocation rows coexist in order.
- `TestRecordAgentInvocation` — first delta = cumulative, second = delta only, never negative, failed export keeps cursor, fork restarts, monotonic across a compaction bump.
- `TestAgentAttribution` — agent + serialized model persisted, missing attribution preserves prior values, review rounds/models get distinct rows.
- `TestCompactionReducesContext` — shrink logs at info; unchanged/grown warns; unavailable context does not warn.
- `TestOpencodeSupportsCompaction`, `TestCaptureAgentSession`, `TestContextCompaction` updated for the version-aware paths.

---

## Follow-ups

- **Aggregate inflation 1.00–1.05x** is a post-deploy measurement on real data, not something the test suite can assert; the delta model makes it exact at session granularity by construction.
- The opencode version stays **unpinned** (`Dockerfile:14` floats on `opencode.ai/v2/install`), recorded as an accepted risk in MNT-251 §12. The startup smoke test converts the next silent CLI break into a loud deploy-time failure.
- Re-run the compaction monotonicity probe once compaction genuinely rewrites a session (the spike probe compacted nothing); v2 has no CLI path yet — `opencode api` remains the candidate.

## References

- Related: [[2026-10-16-opencode-v2-session-token-accounting]] — the v2 ground truth and Phase 0 measurements this build follows
- Related: [[2026-07-07-add-context-compaction]] — compaction was recorded as "live" while it was a no-op; corrected here
- Related: [[2026-07-16-session-history-tokens-null]] — the file-backed export this build keeps
- Related: [[2026-08-19-build-agent-stale-session-deleted-worktree]] — the stale-pointer incident this build closes
- Related: [[2026-07-23-session-tokens-audit-revalidation]] — cumulative-vs-delta and cache-inclusive totals
- Related: [[2026-09-30-mnt-228-intermediate-history-states]] — the two-writer step-row rule this build supersedes
- Related: [[2026-08-25-mnt-181-total-tokens-counter]] — the total this build re-points at `kind='invocation'`
- Related: [[2026-07-23-session-history-modal]] — the history endpoint this build re-keys by `task_id`
- External: https://linear.app/mnt/issue/MNT-251
