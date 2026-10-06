---
title: MNT-230 — Switchable agent harness (OpenCode / Claude Code)
date: 2026-09-30
type: implementation
status: resolved
session_id: -
services: [agents, workflows, settings, library, persistence, mcp]
branch: mnt-230-claude-support
tickets: [MNT-230]
tags: [claude-code, opencode, harness, agents, review, mcp, environment]
related:
  - 2026-09-30-claude-code-harness-build-plan
  - 2026-09-16-mnt-205-revise-merged-environment
  - 2026-09-14-opencode-agent-prompts-hardening
  - 2026-08-19-build-agent-stale-session-deleted-worktree
  - 2026-08-04-fix-resolve-agent-truncated-context
  - 2026-08-28-awaiting-input-workflow-continues-to-review
---

# MNT-230 — Switchable agent harness (OpenCode / Claude Code)

## TL;DR

Implemented the build plan in [[2026-09-30-claude-code-harness-build-plan]]: a new `AGENT_HARNESS` setting
(`opencode` | `claude`) resolved through `SessionEnvironment`, a `demetra/services/agents/claude.py` wrapper around the
`claude -p` CLI, and a `demetra/services/agents/harness.py` facade every workflow now imports instead of `opencode.py`
directly. Two things in the plan didn't survive contact with the real CLI and were adapted: there is no `--max-turns`
flag (a USD budget cap is the real bound instead), and Claude cannot `--resume` a session under a different `--agent` —
the build step now gets its own fresh session, never the plan's. `sessions.harness` pins the harness per session so a
mid-ticket switch never resumes a foreign session id. Full test suite (1014 tests), ruff, ty and pre-commit all green.

---

## Overview

The plan document ([[2026-09-30-claude-code-harness-build-plan]]) already captures the target design in detail; this
page records what changed on contact with the real, installed `claude` CLI (v2.1.285) and the final shape of the code.

Layering, unchanged from the plan:

```
workflows/*  ──►  services/agents/harness.py  ──┬─►  services/agents/opencode.py   (unchanged)
services/vcs ──►        (dispatch on             └─►  services/agents/claude.py     (new)
                         environment.agent_harness)
```

## Step 1 — CLI verification found two real deviations

Before writing `claude.py`, the plan's own "Verify before coding" section was run against the installed CLI:

- `--agents <json>` + `--agent <name>` works with `-p` and inline JSON (not just a file path, despite the `--help` text
  reading that way).
- `--effort`, `--session-id`, `--resume`, `--mcp-config` (`{"mcpServers": {...}}` shape), `permission_denials` in the
  result event — all confirmed exactly as planned.
- **No `--max-turns` flag exists in this CLI version**, and `maxTurns` set in the agent JSON or in an on-disk
  `.claude/agents/*.md` frontmatter file does **not** cap a top-level `-p --agent` run (tested empirically: a
  `maxTurns: 1` agent still ran 3 turns to completion). `--max-budget-usd` does work and is real — a run capped at
  `$0.0001` came back with `is_error: true`, `subtype: "error_max_budget_usd"`, `terminal_reason: "budget_exhausted"`.
  **Decision:** replaced the plan's turn-cap guard with a per-agent USD budget cap
  (`settings.CLAUDE_MAX_BUDGET_USD` + `CLAUDE_<AGENT>_MAX_BUDGET_USD` overrides, `--max-budget-usd` always passed),
  detecting failure via `subtype in {"error_max_turns", "error_max_budget_usd", "error_during_execution"}`.
  `error_max_turns` is kept in the failure set in case a future CLI version adds real turn-cap support without a code
  change here. `num_turns` is still parsed and reported for observability even though it isn't enforced.
- Project slug format under `~/.claude/projects/` confirmed: every character that is not `[A-Za-z0-9]` (not just `/`)
  becomes `-` — verified with a path containing dots (`/private/tmp/claude.verify.dots` →
  `-private-tmp-claude-verify-dots`).

## Step 2 — Cross-agent `--resume` does not switch persona

Not in the original plan, found while implementing `workflows/build.py`: Claude Code's `--system-prompt-snapshot`
behavior (visible in `--help`) records the system prompt on a conversation's first request and replays it verbatim on
every later request or resume — including across a `--resume` with a different `--agent`. That means the plan's
original design (build resumes the plan agent's session id under `--agent build-agent`) would silently keep answering
as the read-only, no-edit plan agent forever.

**Fix:** `workflows/build.py::run_build_step` now calls `harness.new_session_id(environment=context.environment)` for
its own session, ignoring `context.session_id` (the plan's session) entirely on Claude. `new_session_id` returns `None`
on OpenCode, so `build_session_id = harness.new_session_id(...) or context.session_id` preserves the exact prior
behavior there. This id is threaded explicitly into the two call sites that need it — `harness.build_agent(session_id=
build_session_id, ...)` and `check_and_compact_context(context, session_id=build_session_id)` — and reused across every
iteration of the build retry loop, so resuming stays safe (always the same agent). It is deliberately **not** persisted:
a first attempt at this (`save_session(..., harness=...)` reassigning `context.session`) was reverted after review —
overwriting the canonical, plan-linked `session_id` would have made `sessions.session_id` mean "whichever agent session
last touched this ticket" instead of "the session for this ticket," breaking traceability back to the plan conversation
for no benefit (a process restart losing build's conversational memory is an accepted, already-precedented tradeoff; see
`2026-08-19-build-agent-stale-session-deleted-worktree`). Every other call site (`review`, `lint`, `cleanup`) keeps
reading `context.session_id` unchanged.

## Step 3 — Session pinning

`sessions.harness` (migration `b4c5d6e7f8a9_add_sessions_harness_column`, default `'opencode'`) records which harness a
session last ran under. `workflows/setup.py::setup_workflow` compares the stored value against
`environment.agent_harness` on every re-entry (not just once): a mismatch calls
`reset_session_harness(task_id, harness)` — a plain `UPDATE` that clears `session_id` and re-pins `harness`,
independent of and before the next `save_session` upsert — then mutates the in-memory `Session` the same way. Because
the DB write happens immediately, a crash right after a harness switch still leaves a consistent row for the next
re-entry (idempotent), satisfying the "durable across re-entry" rule from
[[2026-08-28-awaiting-input-workflow-continues-to-review]].

One related gap surfaced and was fixed in the same pass: `save_session`'s `ON CONFLICT` clause preserves the old
`session_id` when the new one is empty (`COALESCE(NULLIF(..., ''), sessions.session_id)`), so clearing a session id
could never go through `save_session` itself — `reset_session_harness` uses a direct `UPDATE` instead. Two other raw
`RETURNING`/column lists in `persistence/database.py` (`upsert_pending_session`, and the `Session`-from-row
constructors) needed the new `harness` column added by hand since they don't select `*`.

## Step 4 — Tool policy and Linear scope

`.claude/agents/*.md` (8 files, one per OpenCode agent) hold YAML frontmatter (`name`, `description`, `tools`) plus the
system-prompt body, addressed from `BASE_PATH` (a Demetra asset, not a worktree path — the CLI's own `.claude/agents`
discovery wouldn't find them anyway since cwd is the worktree). `claude.py::load_claude_agent_definition` parses them at
runtime and injects Linear/web tools by agent name (`CLAUDE_LINEAR_READ_TOOLS` for plan/resolve/research,
`CLAUDE_LINEAR_CREATE_TOOLS` for research only) plus the shared `Bash(git commit:*)`/`Bash(git push:*)` deny list —
enforced twice, once in the `--agents` JSON and again via `--allowedTools`/`--disallowedTools` on the CLI.

**Open item:** `CLAUDE_LINEAR_READ_TOOLS`/`CLAUDE_LINEAR_CREATE_TOOLS` (`demetra/library/constants.py`) list plausible
Linear MCP tool names sourced from general knowledge of Linear's MCP server, not from an authenticated `/mcp` session —
the plan's own verification step for this required OAuth login, which wasn't available in this session. **Confirm the
exact tool names against a live `claude` session (`/mcp`) before relying on the research/plan/resolve agents' Linear
access.**

## Test Results

```
uv run ruff check .        # All checks passed
uv run ty check             # All checks passed
uv run pre-commit run --all-files   # all hooks passed
uv run pytest tests/ -q     # 1014 passed
uv run alembic -x url=sqlite:///:memory: upgrade head   # chain intact
```

New: `tests/test_claude.py`, `tests/test_harness.py`, `tests/test_setup_workflow.py`. Extended:
`tests/test_session_environment.py`, `tests/test_settings.py`, `tests/test_migrations.py`, `tests/test_workflows.py`
(harness-switch build-session-pinning case). Updated import paths only (no behavior change intended):
`tests/test_validate_workflow.py`, `tests/test_merge_service.py`, `tests/test_rebase_service.py`,
`tests/test_subprocess.py`.

---

## Follow-ups

- Confirm real Linear MCP tool names via an interactive `claude` session (`/mcp`) and adjust
  `CLAUDE_LINEAR_READ_TOOLS`/`CLAUDE_LINEAR_CREATE_TOOLS` if they differ.
- `claude login` and one-time Linear MCP OAuth (`claude mcp login linear` equivalent, or `/mcp` in an interactive
  session) are still manual host setup steps, per the plan's "Host setup and docs" section — not exercised end-to-end
  against a real ticket in this session.
- Docker image support, Cursor/CodeRabbit cleanup and a React harness-toggle UI remain out of scope for v1, as decided
  in the build plan.

## References

- Related: [[2026-09-30-claude-code-harness-build-plan]], [[2026-09-16-mnt-205-revise-merged-environment]],
  [[2026-09-14-opencode-agent-prompts-hardening]], [[2026-08-19-build-agent-stale-session-deleted-worktree]],
  [[2026-08-04-fix-resolve-agent-truncated-context]], [[2026-08-28-awaiting-input-workflow-continues-to-review]]
- External: MNT-230
