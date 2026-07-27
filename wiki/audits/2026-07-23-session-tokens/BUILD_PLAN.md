# Session Tokens Updates - Build Plan (MNT-145)

> **Audience:** implementation agent (e.g. Sonnet). Full background in
> `wiki/audits/2026-07-23-session-tokens/RESULT.md` (revalidated 2026-07-23) and
> `wiki/pages/2026-07-23-session-tokens-audit.md`. Read the
> "Corrections" section there before changing anything — several intuitive
> "fixes" were already refuted.

## TL;DR

Context compaction is disabled (`build.py:77`, MNT-145) because its threshold check
compared a **cumulative** session token counter against a 100k **context** threshold —
so `/compact` fired on every build iteration. Fix: derive the **current context size**
from the last assistant message in the `opencode export` payload, use *that* for the
threshold check, then re-enable the call. Along the way, add `model` and
`context_tokens` columns to `session_history`, and cap the plan text shipped to Groq.

## Hard constraints — do NOT

- **Do not** reorder `record_session_step_history` vs `git_cleanup` in
  `demetra/workflows/cleanup.py`. Recording already happens before cleanup; the old
  NULL-row bug was pipe truncation, fixed 2026-07-17 (see
  `wiki/pages/2026-07-16-session-history-tokens-null.md`).
- **Do not** add a TTL cache around `opencode export` — it runs once per build
  iteration (minutes apart); a cache would never hit.
- **Do not** replace `run_command_to_file` with `run_command` in
  `get_opencode_session_tokens` — the temp-file redirect works around a 64 KB pipe
  truncation in `opencode export`.
- **Do not** use `TokenUsage.total` (or any cumulative sum, including
  `input + output + reasoning`) for the compaction decision — cumulative counters only
  grow and will always exceed the threshold.
- **Do not** backfill or sentinel-tag the four all-NULL sessions from 2026-07-16/17.
  Leave the rows as-is; SQL aggregates already ignore NULLs.

---

## Step 1 — Inspect a live `opencode export` payload (blocking prerequisite)

The current parser (`demetra/services/opencode.py:142`) only reads session-level
`info.tokens.*`, which are cumulative. The current-context metric must come from the
**last assistant message's** per-message token usage.

1. Run `opencode export <session_id>` against any real session (any opencode session on
   this machine works; `opencode session list --format json` lists them). Save the
   output to a scratch file.
2. Locate the per-message token structure — expected shape is a `messages` (or similar)
   array where assistant entries carry `tokens.{input,output,reasoning}` and
   `tokens.cache.{read,write}`. Record the exact key paths; the parser in Step 2 must
   match reality, not this plan's guess.
3. While you're in the payload, note whether `tokens.cache.write` is ever non-zero
   (audit recommendation 5). If the key genuinely never exists for these models, leave
   the column but note it in the PR description.
4. Current context size for a message ≈ `input + cache_read` of the **latest assistant
   message** (that is what filled the window on the last request). Confirm the numbers
   are plausible (≤ model context, e.g. a few hundred k at most — not tens of millions).

If the export format has no per-message tokens at all, stop and report back instead of
improvising a metric.

## Step 2 — Extract current context size in `opencode.py`

**File:** `demetra/services/opencode.py`

1. Add a `context: int | None = None` field to `TokenUsage`
   (`demetra/library/models.py:45`) — `None` when the per-message data is unavailable.
   Keep the existing `total` property unchanged (it feeds the `length` column,
   observability only).
2. In `get_opencode_session_tokens`, after parsing `info.tokens`, walk the messages
   array (key paths from Step 1), find the last assistant message with token data, and
   set `usage.context = input + cache_read` (adjust to the real schema). Malformed or
   missing message data must degrade to `context=None`, never raise — mirror the
   defensive style already used for the `cache` block (`opencode.py:184-191`).
3. Every value goes through `non_negative_int` (`demetra/services/utils.py:119`), same
   as the existing fields.

## Step 3 — Migration: add `context_tokens` and `model` columns

**Files:** new `migrations/versions/<rev>_add_session_history_context_model_columns.py`,
`demetra/library/tables.py:97`, `demetra/library/models.py:58` (`SessionHistory`),
`demetra/services/database.py` (`record_session_history` at ~`:491`,
`record_session_step_history` at ~`:942`).

1. Run `uv run alembic heads` to get the current head for `down_revision` (follow the
   pattern in `migrations/versions/a2b3c4d5e6f7_add_session_history_token_columns.py`).
2. Add nullable columns: `context_tokens Integer`, `model String`.
3. Thread both through the `session_history` Table, the `SessionHistory` dataclass,
   `record_session_history`, and `record_session_step_history` (new optional
   `model: str | None = None` parameter; `context_tokens` comes from `usage.context`).
4. Callers pass the model that produced the step:
   - `plan` (`demetra/workflows/plan.py:82`) → `OPENCODE["plan_model"]`
   - `build` (`demetra/workflows/build.py:33`) → `OPENCODE["build_model"]`
   - `completed` / `failed` (`demetra/workflows/cleanup.py:69` / `:95`) →
     `OPENCODE["build_model"]`
   (`OPENCODE` config lives at `demetra/settings.py:111`.)

## Step 4 — Fix the threshold check and re-enable compaction

**File:** `demetra/workflows/build.py`

1. In `check_and_compact_context` (`build.py:19`), replace the
   `length > CONTEXT_COMPACTION_THRESHOLD` comparison with the context metric:
   use `usage.context` when available; when it is `None`, skip compaction (do not fall
   back to the cumulative `length`). Keep recording the history row exactly as today.
2. Update the `print_message` text to say context size, not session length.
3. Uncomment `await check_and_compact_context(context)` at `build.py:77` and remove the
   `# TODO: MNT-145` line above it.
4. `CONTEXT_COMPACTION_THRESHOLD` (`demetra/settings.py:40`, default 100 000) is now
   compared against genuine context tokens — the default is sensible, leave it.

## Step 5 — Cap plan output sent to Groq

**File:** `demetra/services/groq.py:101` (`extract_plan`)

Truncate `plan_output` to its last ~32 000 characters (≈8k tokens) before invoking the
chain, e.g. `plan_output = plan_output[-32_000:]`. Keep it a module-level constant with
a short comment; the target model is `llama-3.1-8b-instant` (131k context) and plan
outputs can reach hundreds of k tokens.

## Step 6 — Tests and verification

Test layout: `tests/test_opencode.py`, `tests/test_database.py`, `tests/test_groq.py`,
`tests/test_build*.py` — follow existing patterns (they patch `run_command_to_file` for
export tests).

1. `get_opencode_session_tokens`: context extracted from a realistic payload fixture
   (use the Step 1 capture, trimmed); missing/malformed messages → `context=None`;
   existing fields unaffected.
2. `check_and_compact_context`: compacts when `context > threshold`; skips when below;
   skips (and still records) when `context is None`; failure path prints error.
3. `record_session_step_history`: `model` and `context_tokens` persisted; `None`
   defaults preserved.
4. `extract_plan`: input longer than the cap is truncated from the front.
5. Full gate: `uv run pytest`, plus ruff/ty per repo convention (see `Makefile`). All
   pre-existing tests must stay green — several patch `get_opencode_session_tokens` or
   `record_session_step_history`; update their expectations only where signatures
   changed.

## Acceptance criteria

- [ ] `TokenUsage.context` populated from the last assistant message of the export; `None` on any parse gap.
- [ ] `session_history` gains nullable `context_tokens` + `model` columns via one new Alembic migration; recorded on every step.
- [ ] Compaction decision uses `usage.context` only; `build.py:77` re-enabled; MNT-145 TODO removed.
- [ ] `extract_plan` input capped.
- [ ] No changes to cleanup ordering, `run_command_to_file`, or NULL historical rows.
- [ ] Test suite, lint, and type checks pass.
