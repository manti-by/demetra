---
title: Build plan — switchable agent harness (OpenCode / Claude Code)
date: 2026-09-30
type: investigation
status: open
session_id: -
services: [agents, workflows, settings, library, persistence, mcp]
branch: mnt-230-claude-support
tickets: [MNT-230]
tags: [claude-code, opencode, harness, agents, review, mcp, environment, build-plan]
related:
  - 2026-09-16-mnt-205-revise-merged-environment.md
  - 2026-09-14-opencode-agent-prompts-hardening.md
  - 2026-08-19-build-agent-stale-session-deleted-worktree.md
  - 2026-08-04-fix-resolve-agent-truncated-context.md
  - 2026-08-03-wiki-mcp-tools.md
  - 2026-07-23-session-tokens
---

# Build plan — switchable agent harness (OpenCode / Claude Code)

## TL;DR

Add an `AGENT_HARNESS` setting (`opencode` | `claude`) that resolves through `SessionEnvironment`, so a project or user
can switch from OpenCode to Claude Code. A new `demetra/services/agents/claude.py` wraps the `claude -p` CLI. A new
`demetra/services/agents/harness.py` facade dispatches every agent call (plan, resolve, build, validate, review,
review-fixes, merge, rebase, research) plus session and token helpers to the selected harness. The workflows import only
the facade. Per-agent Claude models live in `settings.CLAUDE`, and each one can be overridden in the project or
user-shared env. Review runs a configurable list of `model:effort` pairs in parallel (default `opus:xhigh`), because the Claude CLI has no temperature flag.
Claude agents are defined in `.claude/agents/*.md` and injected per run with `--agents`/`--agent`. MCP is passed inline
with `--mcp-config` (Demetra + Linear, `--strict-mcp-config`). The first target is the host OS, using the current
Claude Code login. Docker comes later.

## Decisions (answered)

- **Harness scope:** `settings.AGENT_HARNESS` default, overridable via project env → user-shared env (the same layers as
  the models). The harness is pinned on the `sessions` row so a mid-ticket switch never resumes a foreign session id.
- **Review variation:** `CLAUDE_REVIEW_MODELS`, a list of `model[:effort]` pairs run in parallel. The default is a single
  `opus:xhigh`. Effort stands in for temperature. More pairs can be added through env.
- **Default models and effort:**
  - plan: `opus`, effort `medium`
  - resolve: `opus`, effort `xhigh`
  - research: `opus`, effort `high`
  - build: `sonnet`, no effort
  - validate: `haiku`, no effort
  - review: `opus:xhigh`
- **Linear tool scope:** read-only Linear tools for all agents. The research agent also gets the Linear issue-creation
  tool.
- **User settings:** runs load the global `~/.claude` settings, hooks and plugins. No `--setting-sources` restriction
  for now.
- **Skills:** all skills (including `fix-review-findings`) are installed in the global `~/.claude/skills`. Claude finds
  them from any worktree, so nothing extra needs to be passed.
- **Auth:** runs on the host OS and reuses the current Claude Code login (keychain / `~/.claude`). `HOME` and `USER` are
  already in `OS_ENV_ALLOWLIST`. No API key plumbing in v1.
- **Agent prompts:** separate Claude subagent files in `.claude/agents/*.md`, one per OpenCode agent.
- **MCP wiki:** the Demetra MCP keeps serving Demetra's own wiki (`BASE_PATH/wiki`). No worktree override.
- **MCP servers:** Demetra + Linear (remote HTTP/OAuth), with `--strict-mcp-config` so user-level MCP servers stay out.
  Playwright is excluded.
- **Live output:** `--output-format stream-json --verbose`, rendered into readable `print_message` lines while the
  agent works; the final result and usage are parsed from the last `result` event.
- **Compaction:** rely on Claude Code auto-compact. No explicit `/compact`. Token usage is still recorded in
  `session_history`.

## Current state (verified in code)

- `demetra/services/agents/opencode.py` has 8 `opencode_*_agent` wrappers → `run_opencode_agent` (`opencode run --dir
  --model --agent [--session] [--title]`, task via stdin). It also has session lookup by title
  (`get_opencode_session_id`), token export (`get_opencode_session_tokens`), `opencode_compact_session`, and the
  `extract_plan` / `extract_research_report` marker helpers.
- Callers: `workflows/plan.py`, `build.py`, `validate.py`, `review.py`, `resolve.py`, `research.py`, `review_fixes.py`,
  `cleanup.py`, plus `services/vcs/merge.py` and `services/vcs/rebase.py`. `services/llm/openrouter.py` lazily imports
  `PLAN_HAS_QUESTIONS`.
- `settings.OPENCODE` (`OpenCodeConfig` in `library/types.py`) holds the path + 5 single models + `review_models`.
- `SessionEnvironment` (`library/models.py:330`) resolves `OPENCODE_*_MODEL` through project → user → settings
  (`_settings_default`, `library/models.py:286`). **Gap:** `review.py:55` reads `OPENCODE["review_models"]` straight
  from settings, so review models can't be overridden per project today.
- The plan step discovers the OpenCode session id afterwards by title (`plan.py:120`). Build continues the same session
  (`--session`).
- `demetra/services/agents/cursor.py` and `coderabbit.py` are unused (only `settings.py` references them). Out of scope.
- `opencode.json` registers `Demetra` MCP as `uv run python -m demetra.mcp_server` (relative to cwd). The MCP wiki tools
  read `BASE_PATH/wiki` (`services/wiki/__init__.py:61`).
- `settings.py` reads `os.environ` only (no dotenv). Agent subprocesses get only `OS_ENV_ALLOWLIST` + project opt-ins
  (`services/runtime/subprocess.py:31`).

## Target design

```
workflows/*  ──►  services/agents/harness.py  ──┬─►  services/agents/opencode.py   (unchanged CLI wrapper)
services/vcs ──►        (dispatch on             └─►  services/agents/claude.py     (new CLI wrapper)
                         environment.agent_harness)
```

- `harness.py` exposes harness-neutral functions with the current signatures: `plan_agent`, `resolve_agent`,
  `build_agent`, `validate_agent`, `review_agent`, `review_fixes_agent`, `merge_agent`, `rebase_agent`,
  `research_agent`, `get_session_id`, `get_session_tokens`, `compact_session`. All of them return `tuple[int, str,
  str]` or the existing types.
- The `PLAN_*` / `RESEARCH_*` markers and the `extract_plan` / `extract_research_report` helpers move from
  `opencode.py` to `demetra/library/constants.py` (markers) and `harness.py` (helpers). `opencode.py` re-imports them,
  so existing imports and tests keep working until they're migrated.

## Build plan

### 1. Settings and types

- `demetra/library/types.py`: add `ClaudeConfig(PathConfig)` with `plan_model`, `resolve_model`, `build_model`,
  `validate_model`, `research_model`, `review_models: list[str]`, and optional per-agent `*_effort: str | None`.
- `demetra/library/constants.py`: add `AGENT_HARNESSES = frozenset({"opencode", "claude"})`, `CLAUDE_EFFORT_LEVELS =
  frozenset({"low", "medium", "high", "xhigh", "max"})`, `CLAUDE_LINEAR_READ_TOOLS` / `CLAUDE_LINEAR_CREATE_TOOLS`
  (explicit Linear MCP tool names, see step 3), and the moved plan/research markers.
- `demetra/settings.py`:
  - `AGENT_HARNESS = env_get_str("AGENT_HARNESS", "opencode")`. Raise `SettingsError` when it's not in
    `AGENT_HARNESSES`, following the `CORS_ALLOWED_ORIGINS` pattern.
  - `CLAUDE: ClaudeConfig`:
    - `path`: `env_get_path("CLAUDE_PATH", HOME_PATH / ".local/bin/claude")`
    - `plan_model`: `CLAUDE_PLAN_MODEL`, default `opus`; `plan_effort`: `CLAUDE_PLAN_EFFORT`, default `medium`
    - `resolve_model`: `CLAUDE_RESOLVE_MODEL`, default `opus`; `resolve_effort`: `CLAUDE_RESOLVE_EFFORT`, default
      `xhigh`
    - `research_model`: `CLAUDE_RESEARCH_MODEL`, default `opus`; `research_effort`: `CLAUDE_RESEARCH_EFFORT`, default
      `high`
    - `build_model`: `CLAUDE_BUILD_MODEL`, default `sonnet`; `build_effort`: `CLAUDE_BUILD_EFFORT`, default `None`
    - `validate_model`: `CLAUDE_VALIDATE_MODEL`, default `haiku`; `validate_effort`: `CLAUDE_VALIDATE_EFFORT`, default
      `None`
    - `review_models`: `CLAUDE_REVIEW_MODELS`, default `["opus:xhigh"]`

    Effort values are validated against `CLAUDE_EFFORT_LEVELS` (`SettingsError`). Aliases track the newest model. Full
    ids such as `claude-opus-5-5` are also accepted. The turn cap and idle watchdog settings are defined in step 4a. Merge, rebase and review-fixes reuse the build model and effort,
    the same as on OpenCode.
- `.env.docker.example`: document the new keys, commented out.

### 2. Environment resolution (`library/models.py`)

- `_settings_default`: add `AGENT_HARNESS`, a `CLAUDE_*_MODEL` / `CLAUDE_*_EFFORT` branch mirroring the `OPENCODE_`
  branch, and `OPENCODE_REVIEW_MODELS` / `CLAUDE_REVIEW_MODELS` (list joined with `,`).
- `SessionEnvironment`:
  - `agent_harness` property. It raises `EnvironmentConfigError` for a value outside `AGENT_HARNESSES`, so a bad
    project env fails the run and rolls it back.
  - `claude_plan_model` … `claude_research_model` properties plus `claude_effort(agent)`. Effort is optional, so it
    returns `None` instead of raising.
  - `review_models` property returning `list[ReviewModel]` for the active harness. It parses `model[:effort]`; OpenCode
    entries never carry effort.
  - `agent_model(agent: str) -> str` returns the model for the active harness. It's used by the workflows for
    `session_history.model` instead of `opencode_*_model`.
- `library/models.py`: add dataclass `ReviewModel(model: str, effort: str | None = None)`.

### 3. Claude subagent definitions (`.claude/agents/`)

- Port the 8 agents from `.opencode/agents/*.md` into Claude subagent format, as `.claude/agents/<name>.md` with the
  same names (`plan-agent`, `build-agent`, …). Frontmatter is `name`, `description`, `tools` (allowlist). Bodies are
  copied verbatim, with OpenCode-specific wording (tool names, `mode`) adapted.
- Tool policy, enforced again on the CLI (step 4) because frontmatter alone isn't a guarantee:
  - `build-agent`, `merge-agent`, `rebase-agent`: `Read, Grep, Glob, Edit, Write, Bash, mcp__demetra__*`.
  - `plan-agent`, `resolve-agent`: read-only plus `Bash`, `mcp__demetra__*` and the read-only Linear tools
    (`CLAUDE_LINEAR_READ_TOOLS`, e.g. `mcp__linear__get_issue`, `mcp__linear__list_issues`,
    `mcp__linear__list_comments`).
  - `research-agent`: the same, plus `WebSearch`, `WebFetch` and the Linear create tools (`CLAUDE_LINEAR_CREATE_TOOLS`,
    e.g. `mcp__linear__create_issue`) so it can file related tickets. It gets no update or delete tools.
  - Linear tools are listed by exact name, never `mcp__linear__*`, so a new write tool on the server isn't picked up
    automatically.
  - `review-agent`, `validate-agent`: read-only plus `Bash`. No `Edit` or `Write`.
  - Every agent gets `Bash(git commit:*)` and `Bash(git push:*)` in its deny list.
- The loader parses the frontmatter and body at runtime from `BASE_PATH / ".claude" / "agents"`. That's a Demetra asset,
  not a worktree path, so `BASE_PATH` is correct here. It builds the `--agents` JSON from them, so the files don't have
  to be installed into `~/.claude/agents` (which would affect the user's own Claude sessions).
- Side effect: these files also show up as project subagents when a developer opens Demetra itself in Claude Code.
  Accepted.

### 4. Claude service (`demetra/services/agents/claude.py`)

- `run_claude_agent(target_path, task, model, agent, session_id=None, resume=False, effort=None, env=None,
  project_id=None, disable_stdio=False) -> tuple[int, str, str]`. The command is:

  ```
  claude -p --output-format stream-json --verbose --model <model> \
         --agents <json of the one agent> --agent <agent> \
         --mcp-config <inline json> --strict-mcp-config \
         --permission-mode acceptEdits \
         --allowedTools <agent allowlist> --disallowedTools "Bash(git commit:*)" "Bash(git push:*)" [Edit Write ...] \
         (--session-id <uuid> | --resume <uuid>) [--effort <level>]
  ```

  - The task goes via stdin (`input_text=task`), the same as OpenCode, to avoid argv truncation
    (`2026-08-04-fix-resolve-agent-truncated-context`).
  - cwd = `target_path` (the worktree). `run_command` already sets `cwd`, and Claude has no `--dir`.
  - `timeout` = `SUBPROCESS_TIMEOUT` (the `run_command` default).
  - Live progress (decision B): stdout is newline-delimited JSON events, which are rendered live and parsed at the end.
    - `format_claude_stream_event(line: str) -> str | None` is a pure formatter. It turns one event into a readable
      line, or `None` to skip it:
      - `system/init`: model and session id
      - assistant `text` blocks: the text
      - `tool_use`: `→ <Tool> <short input>`, e.g. `→ Bash uv run pytest`, `→ Edit demetra/foo.py`
      - `tool_result`: `✓` / `✗`, plus the first line on error
      - `result`: a summary with turns, duration and cost

      Tool results are truncated for display only; the raw line is still captured.
    - `extract_claude_result(stdout: str) -> ClaudeResult` finds the last `{"type": "result"}` event and returns
      `result`, `is_error`, `session_id` and `usage`.
    - The run returns `(exit_code, result.result, stderr)`. If `is_error` is true, it forces a non-zero exit code. If
      no result event exists (crash or timeout), it returns exit `1` with the concatenated assistant text as stdout.
      Callers keep the existing stdout contract.
    - `library/models.py`: add dataclass `ClaudeResult(result: str, is_error: bool, session_id: str | None, usage:
      TokenUsage | None)`.
  - `services/runtime/subprocess.py` / `utils.py`:
    - Add an optional `line_formatter: Callable[[str], str | None] | None = None` parameter to `run_command` →
      `live_stream`. The raw line is always appended to `result`. When a formatter is given, only its non-`None` output
      is echoed to stdout and to `stream_logger`, so logs stay readable. OpenCode passes no formatter, so its behaviour
      is unchanged.
    - Raise the `create_subprocess_exec(limit=...)` stream limit (new `SUBPROCESS_STREAM_LIMIT` setting, e.g. 16 MiB).
      A single stream-json event that carries a file read or a large tool result easily exceeds the 64 KiB `readline`
      default. That is the same crash class as `2026-09-14-listener-readline-limit-crash`.
  - All rendered text goes through `print_message` escaping rules (no raw Rich markup), per
    `2026-07-21-rich-markuperror-and-run-attempts`.
  - Don't use `bypassPermissions`. It runs on the host with the user's credentials. In `-p` mode, tools outside
    `--allowedTools` are denied instead of prompting.
- Thin wrappers mirror OpenCode: `claude_plan_agent` (same plan-format suffix), `claude_build_agent`,
  `claude_review_agent(model, effort)`, `claude_validate_agent`, `claude_review_fixes_agent`, `claude_merge_agent`,
  `claude_rebase_agent`, `claude_resolve_agent`, `claude_research_agent`. They reuse `get_prompt(...)` exactly as the
  OpenCode wrappers do.
- `build_claude_mcp_config(project_id) -> str` returns inline JSON:
  - `demetra`: `{"type": "stdio", "command": str(UV["path"]), "args": ["--directory", str(BASE_PATH), "run",
    "--env-file", str(BASE_PATH / ".env"), "python", "-m", "demetra.mcp_server"]}`.
    - `--directory` is needed because cwd is the target worktree, not Demetra.
    - `--env-file` is needed because the MCP subprocess only inherits the allowlisted env, so the DB tools would
      otherwise lack credentials. **Secrets are never written into the JSON or argv.**
  - `linear`: `{"type": "http", "url": "https://mcp.linear.app/mcp"}`. OAuth is done once on the host (see step 9).
- Sessions:
  - `new_claude_session_id() -> str` returns a uuid4. The plan step passes it with `--session-id`, so there's no
    lookup by title after the fact.
  - `get_claude_session_tokens(target_path, session_id) -> TokenUsage | None` parses the transcript
    `~/.claude/projects/<slug(target_path)>/<session_id>.jsonl`:
    - `input`, `output`, `cache_read`, `cache_write` are summed from assistant `message.usage`.
    - `context` is the last assistant `input_tokens + cache_read_input_tokens`.
    - `reasoning` is `0`, because Claude doesn't report it separately.

    It returns `None` on a missing or malformed file, the same contract as `get_opencode_session_tokens`.
  - `claude_session_exists(target_path, session_id) -> bool` checks that the transcript exists. When it doesn't (for
    example after a worktree was recreated, see `2026-08-19-build-agent-stale-session-deleted-worktree`), the build
    starts a fresh `--session-id` instead of failing on `--resume`.
  - `claude_compact_session` is a no-op that returns `(0, "", "")` (auto-compact decision).

### 4a. Headless run guards (hooks, denials, loops)

These cover the ways a headless run can stall or loop: a deny/retry loop, a `Stop` hook that keeps sending the agent
back to work, and a hung hook or MCP call. Each one should end the run in minutes, not after the 30-minute
`SUBPROCESS_TIMEOUT`.

- **Turn cap:**
  - `settings.CLAUDE` gains `max_turns: int` (`CLAUDE_MAX_TURNS`, default `100`) and per-agent overrides
    `CLAUDE_<AGENT>_MAX_TURNS`. The suggested default for build, merge, rebase and review-fixes is `200`.
  - `SessionEnvironment.claude_max_turns(agent) -> int` resolves the value through project → user → settings, the same
    way as the models.
  - `run_claude_agent` always passes `--max-turns <n>`.
  - When the cap is hit, the result event has `subtype == "error_max_turns"`. The run returns a non-zero exit code and
    stderr `Claude agent <agent> stopped: max turns (<n>) reached`.
- **Idle watchdog:**
  - New setting `CLAUDE_IDLE_TIMEOUT` (seconds, default `900`).
  - `run_command` / `live_stream` gain `idle_timeout: int | None = None`. On stdout, each `readline()` is wrapped in
    `asyncio.timeout(idle_timeout)`. When it expires, the process is killed and exit code `-2` is returned with stderr
    `Command idle for <n>s, killed`. `-1` stays reserved for the overall timeout.
  - OpenCode passes `None`, so its behaviour is unchanged.
  - The value must be larger than the longest Bash tool call. Claude's Bash tool is capped by `BASH_MAX_TIMEOUT_MS`
    (10 minutes by default), and a quiet `pytest` run emits no events while it runs. `SettingsError` if
    `CLAUDE_IDLE_TIMEOUT` is less than 660 seconds or larger than `SUBPROCESS_TIMEOUT`.
- **Surfacing permission denials:**
  - `ClaudeResult` gains `subtype: str`, `num_turns: int`, and `permission_denials: list[str]` (tool name plus a short
    input from the result event's `permission_denials`).
  - Every denial is logged as a warning through `print_message`, together with the agent name. This covers expected
    denials such as a blocked `git commit` in a run that otherwise finishes normally.
  - The run fails (non-zero exit code; stderr lists the subtype, turn count and denied tools) when the result has
    `is_error`, is `error_max_turns` or `error_during_execution`, or is missing.
  - Callers keep their existing error paths:
    - build and research raise on a non-zero exit (`BuildError`, or the error that step already raises)
    - validate, merge and rebase follow their current exit-code handling
    - `run_review_agents` drops a failed review run with a warning instead of feeding its partial stdout into the
      summary

  A denial on its own doesn't fail the run; it fails only together with one of the failure outcomes above.

### 5. Harness facade (`demetra/services/agents/harness.py`)

- Each function takes `environment: SessionEnvironment` and dispatches on `environment.agent_harness`. Models come from
  `environment` and are never read from settings directly.
- `review_agents(target_path, environment, env, project_id) -> list[tuple[int, str, str]]` runs
  `environment.review_models` concurrently with `asyncio.gather`. It passes `effort` only on Claude.
- `get_session_id(...)`: on OpenCode it keeps the title lookup; on Claude it returns the id generated before the plan
  run.

### 6. Workflow and VCS wiring

- Replace the `demetra.services.agents.opencode` imports in the following files with the `harness` facade:
  - `workflows/plan.py`, `build.py`, `validate.py`, `review.py`, `resolve.py`, `research.py`, `review_fixes.py`,
    `cleanup.py`
  - `services/vcs/merge.py`, `services/vcs/rebase.py`
- `review.py`: drop `from demetra.settings import OPENCODE`. `run_review_agents` requires `environment` (it's already
  passed from `build.py:131`).
- Replace `context.environment.opencode_*_model` in the `record_session_step_history` calls (`plan.py:154`,
  `build.py:43`, `cleanup.py:131,176`) with `context.environment.agent_model(...)`.
- `plan.py`: on Claude, generate the session id before `plan_agent`, pass it through, and persist it with
  `save_session`. That removes the "No session found" branch for Claude.
- `services/llm/openrouter.py`: import `PLAN_HAS_QUESTIONS` from `library/constants.py`. This removes the lazy import
  from the agents layer.

### 7. Session pinning (DB)

- Migration `add_sessions_harness_column`: `sessions.harness VARCHAR NOT NULL DEFAULT 'opencode'`. Existing rows are
  OpenCode sessions.
- `save_session` writes `environment.agent_harness`.
- On re-entry, if the stored harness differs from `environment.agent_harness`, keep `build_plan`, drop the stored
  `session_id` (start a fresh session on the new harness), set the new harness, and print a warning. This check runs
  durably on every re-entry, not only in the current run (the CLAUDE.md session-state pitfall).
- Run `make check-migrations`.

### 8. Tests (real fixtures, mock only the CLI subprocess)

- `tests/test_claude.py` (new):
  - command construction per agent (allowlist, denylist, `--session-id` vs `--resume`, `--effort` only when set, stdin
    task)
  - `format_claude_stream_event` per event type, with fixture NDJSON lines: init, text, tool_use, tool_result
    ok/error, result, unknown type → `None`, malformed line → `None`
  - `extract_claude_result` (success, `is_error`, missing result event, malformed lines interleaved)
  - `run_command` with `line_formatter`: raw lines captured, only formatted lines echoed. A line over 64 KiB doesn't
    crash.
  - `build_claude_mcp_config`: no secrets, absolute `--directory`
  - transcript token parsing (fixture JSONL under `tmp_path`)
  - the missing-transcript fallback
  - guards:
    - `--max-turns` is always passed, and per-agent overrides are resolved from env
    - an `error_max_turns` result → non-zero exit, with the message in stderr
    - `permission_denials` on a successful run → warning only, exit `0`
    - denials plus `is_error` → non-zero exit, with the denied tools listed in stderr
- `tests/test_subprocess.py`: an idle watchdog test (a script that prints one line and then sleeps longer than
  `idle_timeout` → killed, exit `-2`, captured output kept), and `idle_timeout=None` behaving unchanged.
- `tests/test_workflows.py`: the review fan-out drops a failed Claude review run and keeps the others.
- `tests/test_harness.py` (new): dispatch per harness, and review fan-out with `model:effort` parsing.
- `tests/test_session_environment.py`:
  - `AGENT_HARNESS` layering and the invalid-value error
  - `CLAUDE_*` layering
  - `review_models` override from project env, which is new for OpenCode too
  - `agent_model`
- `tests/test_settings.py`: `CLAUDE` defaults and the `AGENT_HARNESS` `SettingsError`.
- Update `tests/test_workflows.py`, `test_validate_workflow.py`, `test_merge_service.py`, `test_rebase_service.py`, and
  `test_openrouter.py` for the new import paths.
- Harness-switch re-entry test (session row with `harness='opencode'`, env `claude` → fresh session id, plan kept).
- `tests/test_migrations.py` covers the new migration.

### 9. Host setup and docs

- Host prerequisites:
  - the `claude` CLI installed (`CLAUDE_PATH`), and logged in with `claude` → `/login`
  - Linear MCP authorised once, in an interactive `claude` session with the same MCP server name `linear` → `/mcp`
- If `PARENT_HOME` sandboxing is used, extend `services/auth/copy.py` to copy `~/.claude/` (credentials) the same way it
  copies `~/.config/opencode`.
- `AGENTS.md`: document `AGENT_HARNESS`, `CLAUDE` settings, `services/agents/harness.py` / `claude.py`, and
  `.claude/agents/`.
- Add a wiki page under `wiki/pages/` after implementation.
- Out of scope for v1: Docker image (install the CLI, mount credentials, token env), Cursor/CodeRabbit cleanup, React UI
  for the harness toggle (the env editor already covers it).

## Verify before coding (CLI flags on the installed version)

Run `claude --help` on the host and confirm each item. If one is missing, adjust step 4.

- `--agents <json>` + `--agent <name>`. Fallback: `--system-prompt-file` with the agent body, plus
  `--allowedTools` / `--disallowedTools`.
- `--effort <level>`, including `xhigh`. Fallback: `--settings '{"effortLevel": "<level>"}'`. Models that don't
  support effort (e.g. `haiku`) must just omit it.
- The exact Linear MCP tool names for the read and create allowlists: list them in an interactive `claude` session →
  `/mcp`.
- `--resume <id>` re-applies `--agent` / system prompt on resume. The plan and build steps share one session but use
  different agents.
- Transcript path slug format under `~/.claude/projects/`.
- Deny rules (`--disallowedTools "Bash(git push:*)"`) take precedence over `--allowedTools Bash`.
- `--max-turns` is supported in `-p` mode. The result event reports `subtype: "error_max_turns"` and includes
  `permission_denials` and `num_turns`.

## Risks

- **Host credentials:** agents run as the logged-in user with the user's Claude subscription and Linear OAuth. Keep the
  tool allowlists tight, never use `bypassPermissions`, and keep `--strict-mcp-config`.
- **Global Claude config applies:** by decision, `~/.claude/CLAUDE.md`, hooks and plugins load in Demetra runs. Hooks
  that deny, loop or hang are bounded by the step 4a guards (turn cap, idle watchdog, denial reporting). If the global
  hooks keep tripping them, revisit `--setting-sources project,local` or `disableAllHooks`. Before the first real
  ticket, smoke-run each agent on the host against a scratch worktree and read the denials it reports.
- **Stream format drift:** the stream-json event schema isn't a stable contract. The formatter must ignore unknown
  event types and fields, never raise. The final result falls back to the concatenated assistant text.
- **Research ticket creation:** the research agent can create Linear issues, and the research workflow already creates a
  related ticket itself. The research prompt must say which of the two owns ticket creation, so tickets aren't
  duplicated.

## Open questions

None. Remaining unknowns are CLI-behaviour checks under "Verify before coding".
