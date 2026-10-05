---
title: Forward LangSmith env vars to agent subprocesses via SessionEnvironment
date: 2026-09-30
type: implementation
status: resolved
session_id: -
services: [agents, settings, library]
branch: clickup-tracker-support
tickets: []
tags: [langsmith, opencode, claude, environment, tracing, subprocess]
related:
  - 2026-09-28-compose-langsmith-host-env
  - 2026-09-30-mnt-230-claude-code-harness
  - 2026-09-30-clickup-issue-tracker-support
---

# Forward LangSmith env vars to agent subprocesses via SessionEnvironment

## TL;DR

A `403 Client Error: Forbidden` LangSmith warning appearing right after the plan agent
step turned out to come from `langchain-core`'s tracer reading `LANGSMITH_TRACING`/
`LANGSMITH_API_KEY` straight out of the host process's `os.environ` during
`extract_plan()`'s **in-process** LangChain call — nothing to do with
`OS_ENV_ALLOWLIST` or the OpenCode plugin from [[2026-09-28-compose-langsmith-host-env]].
Separately, added `SessionEnvironment.langsmith_env` so LangSmith config resolves
project → user-shared → settings like every other integration config, and forwarded it
into every OpenCode/Claude agent subprocess. Both `LANGSMITH_TRACING` (read by the
`langsmith`/`langchain-core` Python SDK) and `TRACE_TO_LANGSMITH` (read by the
`@langchain/langsmith-opencode` plugin) are set from the same resolved flag, since the
two consumers do not share an env var name. Tracing is forced off when no API key
resolves, so a subprocess never attempts to ingest with an empty key.

---

## Diagnosis: two independent LangSmith paths

**Path 1 — in-process (this session's original bug).** The plan agent itself runs
sandboxed via `OS_ENV_ALLOWLIST` (`demetra/services/runtime/subprocess.py`), so it never
sees `LANGSMITH_*`. Right after, `extract_plan()` (`demetra/workflows/plan.py`) runs
"build plan extraction" **in-process** via `demetra/services/llm/openrouter.py` →
`build_llm()` → `langchain_openai.ChatOpenAI`. `langsmith.utils.tracing_is_enabled()`
(`langsmith/utils.py:121-142`) reads `LANGSMITH_TRACING`/`LANGCHAIN_TRACING_V2` directly
from `os.environ` via `get_env_var(namespaces=("LANGSMITH", "LANGCHAIN"))`, completely
bypassing `demetra/settings.py`. The dev shell had `LANGSMITH_TRACING=true` and a
`LANGSMITH_API_KEY` exported (not from `.zshrc`/`.zprofile`/`.bashrc`/`.profile` — set ad
hoc in the terminal), and the key was invalid/revoked, so the post-call trace POST to
`api.smith.langchain.com/runs/multipart` came back 403. Caught internally and only
logged as a `WARNING` — plan extraction itself was not broken. User rotated the key in
`.env`, which resolves this specific instance; the underlying behavior (langsmith reads
raw `os.environ`, independent of Demetra's config layers) is inherent to the SDK and
cannot be suppressed from application code.

**Path 2 — OpenCode subprocess (documented but never wired up).**
[[2026-09-28-compose-langsmith-host-env]] found that `docker-compose.yaml` forwards
`LANGSMITH_*` into the container's OS env, but `OS_ENV_ALLOWLIST` then drops it before
`opencode` starts (its Gap 1), and even if it didn't, the plugin reads only
`TRACE_TO_LANGSMITH`, never `LANGSMITH_TRACING` (its Gap 2). That analysis assumed the
only route into a subprocess was the host-OS allowlist. This session took a different
route per explicit direction: resolve LangSmith config the same way every other
integration config resolves (`SessionEnvironment`, project → user-shared → settings) and
forward it explicitly, rather than widening `OS_ENV_ALLOWLIST`.

## Implementation

**File:** `demetra/library/types.py` — `LangSmithConfig` TypedDict (`tracing: bool`,
`endpoint: str`, `api_key: str | None`, `project: str`), next to `OpenRouterConfig`.

**File:** `demetra/settings.py` — `LANGSMITH: LangSmithConfig` reads
`LANGSMITH_TRACING`/`_ENDPOINT`/`_API_KEY`/`_PROJECT` via the usual `env_get_*` helpers,
mirroring `OPENROUTER`.

**File:** `demetra/library/models.py`:
- `_settings_default()` (since moved to `demetra/services/settings.py` as `settings_default()`) gained the four
  `LANGSMITH_*` key mappings, same pattern as `OPENROUTER_*`.
- New `SessionEnvironment.langsmith_env` property returns a `dict[str, str]` ready to
  merge into a subprocess env:
  ```python
  tracing = self.get("LANGSMITH_TRACING").strip().lower() in {"true", "1", "yes", "on"}
  try:
      api_key = self.get("LANGSMITH_API_KEY")
  except EnvironmentConfigError:
      api_key = ""
  enabled = "true" if tracing and api_key else "false"
  return {
      "LANGSMITH_TRACING": enabled,
      "TRACE_TO_LANGSMITH": enabled,
      "LANGSMITH_ENDPOINT": self.get("LANGSMITH_ENDPOINT"),
      "LANGSMITH_API_KEY": api_key,
      "LANGSMITH_PROJECT": self.get("LANGSMITH_PROJECT"),
  }
  ```
  `LANGSMITH_API_KEY` is optional (settings default is `None`), so it uses the same
  try/except-around-`.get()` pattern as `claude_effort`; `LANGSMITH_TRACING` always
  resolves because settings always provides `"true"`/`"false"`.

**File:** `demetra/services/agents/opencode.py` — `run_opencode_agent` now merges
`environment.langsmith_env` (when `environment` is given) under the explicit `env`
override, replacing its previous "Reserved; not used" docstring. `opencode_review_agent`
gained an `environment` parameter (previously the only opencode wrapper without one) and
threads it through.

**File:** `demetra/services/agents/claude.py` — `run_claude_agent` gained an
`environment` parameter and the same merge; all 9 wrapper functions
(`claude_plan_agent` … `claude_research_agent`) now pass `environment=environment`
through (8 already accepted it but never forwarded it; `claude_review_agent` gained the
parameter, matching `opencode_review_agent`).

**File:** `demetra/services/agents/harness.py` — `review_agents` now passes
`environment=environment` to both `claude_review_agent` and `opencode_review_agent`.

Precedence is `env` (explicit override) wins over `environment.langsmith_env` — same
"per-step overrides sit on top" rule as `build_subprocess_env`.

## Why both `TRACE_TO_LANGSMITH` and `LANGSMITH_TRACING`

Not a duplicate — two different runtimes read two different, non-interchangeable names:

- **Python SDK** (`langsmith/utils.py:121-142`, `tracing_is_enabled()` →
  `get_env_var("TRACING_V2", default=get_env_var("TRACING"))`, namespaces
  `("LANGSMITH", "LANGCHAIN")`): checks `LANGSMITH_TRACING_V2` / `LANGCHAIN_TRACING_V2`,
  then `LANGSMITH_TRACING` / `LANGCHAIN_TRACING`. Never reads `TRACE_TO_LANGSMITH`.
- **`@langchain/langsmith-opencode` plugin** (`src/config.ts`, `getEnvConfig`):
  `process.env.TRACE_TO_LANGSMITH` only, per [[2026-09-28-compose-langsmith-host-env]]'s
  Gap 2. Never reads `LANGSMITH_TRACING`.

`langsmith_env` sets both from one resolved flag so a single Demetra-level "tracing
on/off" decision reaches whichever consumer ends up running.

## Test Results

- `uv run ruff check` / `pre-commit run --files <touched>` — clean.
- `uv run ty check` — clean.
- New coverage: `tests/test_session_environment.py::TestSessionEnvironmentLangSmith` (5
  tests: settings fallback, both flags set together, tracing forced off without a key,
  project-over-user-over-settings precedence, endpoint/project override), plus merge
  tests in `tests/test_opencode.py::TestRunOpencodeAgentLangSmithEnv` and
  `tests/test_claude.py::TestRunClaudeAgentLangSmithEnv` (no-environment passthrough,
  merge, explicit-`env`-wins).
- `uv run pytest tests/` — 1086 passed, 16 pre-existing failures unrelated to this
  change (all trace back to this dev machine's `AGENT_HARNESS=claude` shell export
  overriding the `"opencode"` default that un-patched tests assume; verified identical
  failures on `git stash` before this session's edits).

## Known follow-up

- The in-process auto-trace behavior (Path 1) is inherent to the `langsmith` SDK reading
  raw `os.environ` and cannot be gated from application code — the only fix is either not
  exporting `LANGSMITH_TRACING=true` without a valid key, or having a valid key (done
  this session).
- `docker-compose.yaml`'s host-env forwarding from [[2026-09-28-compose-langsmith-host-env]]
  is untouched; it is a separate mechanism (container OS env) from the
  `SessionEnvironment`-based forwarding added here, and still has its own Gap 1/Gap 2.

## Note on repo state

This session found the working tree already on `clickup-tracker-support` with a large,
unrelated, uncommitted ClickUp issue-tracker change
([[2026-09-30-clickup-issue-tracker-support]]) spanning several of the same files edited
here (`library/models.py`, `library/types.py`, `settings.py`, `agents/opencode.py`,
`agents/claude.py`, `agents/harness.py`). This work is layered on top of that pre-existing
diff, not merged with it — review hunks carefully before staging/committing since the two
features touch overlapping functions.

## References

- Related: [[2026-09-28-compose-langsmith-host-env]]
- Related: [[2026-09-30-mnt-230-claude-code-harness]]
- Related: [[2026-09-30-clickup-issue-tracker-support]]
- External: [@langchain/langsmith-opencode](https://github.com/langchain-ai/langsmith-opencode)
