---
title: Move settings_default to services and make the suite hermetic to shell env
date: 2026-09-30
type: implementation
status: resolved
session_id: 8fc80821-a613-4826-9cbd-9c201a3f6ee1
services: [library, services, tests]
branch: clickup-tracker-support
tickets: []
tags: [settings, session-environment, layering, tests, agent-harness]
related: [2026-09-16-mnt-205-revise-merged-environment.md, 2026-09-30-mnt-230-claude-code-harness.md, 2026-09-30-clickup-issue-tracker-support.md, 2026-09-30-langsmith-subprocess-env.md]
---

# Move settings_default to services and make the suite hermetic to shell env

## TL;DR

`_settings_default()` — the `settings.py` fallback layer behind `SessionEnvironment.get` — moved out of
`demetra/library/models.py` into a new `demetra/services/settings.py` as the public `settings_default(key)`, so the
library layer no longer carries a lazy `demetra.settings` import. Running the suite afterwards with
`AGENT_HARNESS=claude` and a versioned `CLAUDE_PATH` exposed 16 tests that silently depended on the developer's shell
defaults; an autouse `pin_default_backends` fixture in `tests/conftest.py` plus one assertion fix made the suite pass
under any `AGENT_HARNESS` / `ISSUE_TRACKER` / `CLAUDE_PATH` combination.

---

## Overview

Two independent pieces of work landed on the `clickup-tracker-support` branch (uncommitted at the time of writing):

1. A layering refactor: the settings-fallback helper belongs in `services/`, not `library/`.
2. Hermetic tests: the suite must not change outcome based on what the developer exports in their shell.

The second surfaced only because the first was verified under the user's real environment
(`AGENT_HARNESS=claude`) rather than the default one.

## Step 1 — Move `_settings_default` into `demetra/services/settings.py`

**File:** `demetra/library/models.py` (before)

```python
def _settings_default(key: str) -> str | None:
    from demetra.settings import (AGENT_HARNESS, CLAUDE, ..., OPENROUTER)
    if key == "OPENROUTER_API_KEY":
        return OPENROUTER["api_key"]
    ...
```

**File:** `demetra/services/settings.py` (after)

```python
from demetra import settings

def settings_default(key: str) -> str | None:
    if key == "OPENROUTER_API_KEY":
        return settings.OPENROUTER["api_key"]
    ...
```

- The body is unchanged: the same key → settings mapping for `OPENROUTER_*`, `LANGSMITH_*`, `LINEAR_*`, `ISSUE_TRACKER`,
  `CLICKUP_*`, `AGENT_HARNESS`, `OPENCODE_*_MODEL`, `CLAUDE_*_MODEL|_EFFORT|_MAX_BUDGET_USD`, `*_REVIEW_MODELS`.
- Attributes are read through the `settings` module object **at call time**, not imported by name. This is what keeps
  the existing `patch("demetra.settings.OPENCODE", ...)`-style fixtures in `tests/test_session_environment.py` working
  without modification, and it is what lets the new conftest pin (Step 2) take effect.
- Renamed public (`settings_default`) because a leading underscore no longer fits a function imported across modules.

**File:** `demetra/library/models.py` (after) — the two call sites import lazily:

```python
def get(self, key: str) -> str:
    from demetra.services.settings import settings_default
    ...
    if value := settings_default(key):
        return value
```

```python
@property
def openrouter_config(self) -> OpenRouterConfig:
    from demetra.services.settings import settings_default

    base_url = settings_default("OPENROUTER_BASE_URL")
```

Why lazy: AGENTS.md forbids `library/` → `services/` imports at module load. There is no actual import cycle
(`demetra.settings` → `library.{constants,exceptions,types}` + `services.runtime.utils`, none of which import
`models`), so the local import is purely a layering guard, matching the accepted "circular-avoidance" exception.

Docs touched: `AGENTS.md` services line, and the `_settings_default` mentions in
[[2026-09-30-langsmith-subprocess-env]] and [[2026-09-30-clickup-issue-tracker-support]] now point at the new module.

## Step 2 — Pin the settings-layer harness and tracker defaults in `tests/conftest.py`

**Symptom.** `AGENT_HARNESS=claude uv run pytest tests/` → 15 failures, all in `tests/test_harness.py`
(`TestHarnessDispatch`, `TestHarnessReviewAgents`, `TestHarnessSessionHelpers`) plus
`tests/test_setup_workflow.py::TestSetupWorkflowHarnessSwitch::test_re_entry_with_unchanged_harness_keeps_session_id`.

**Cause.** Those tests build `SessionEnvironment(project_environment={}, user_environment={})` and assert the call
falls through to OpenCode. With both layers empty, `SessionEnvironment.agent_harness` resolves to
`settings.AGENT_HARNESS`, i.e. whatever the shell exported when `demetra/settings.py` was imported. Verified the same
failures reproduce with the Step 1 refactor stashed — pre-existing environment leakage, not a regression.
`tests/test_tracker.py` had already worked around the analogous `ISSUE_TRACKER` leak ad hoc with
`patch("demetra.settings.ISSUE_TRACKER", "linear")`.

**Fix.** **File:** `tests/conftest.py`

```python
@pytest.fixture(autouse=True)
def pin_default_backends(monkeypatch):
    monkeypatch.setattr("demetra.settings.AGENT_HARNESS", "opencode")
    monkeypatch.setattr("demetra.settings.ISSUE_TRACKER", "linear")
```

- Suite-wide rather than per-file so any future test relying on the "no override" path is covered too.
- Tests that want Claude/ClickUp already set it in a project/user layer or `patch(...)` explicitly; both override the
  pin (layers win in `SessionEnvironment.get`; an inner `patch` is applied after the fixture).
- `tests/test_settings.py` uses `importlib.reload(demetra.settings)` inside tests; the reload overwrites the pinned
  attribute for that test only and `monkeypatch` teardown restores it, so the two mechanisms coexist.
- Note `demetra/services/agents/claude.py` imports `ISSUE_TRACKER` by name (tests there patch
  `demetra.services.agents.claude.ISSUE_TRACKER`); the conftest pin does not reach that binding, only the module
  attribute used by `settings_default`.

## Step 3 — Compare the launched binary against `CLAUDE["path"]`

**Symptom.** With the user's real env (`CLAUDE_PATH=~/.local/share/claude/versions/2.1.285`):

```
tests/test_claude.py::TestRunClaudeAgentCommand::test_builds_expected_command
AssertionError: '/Users/.../.local/share/claude/versions/2.1.285'.endswith('claude') is False
```

**Cause.** `run_claude_agent` puts `str(CLAUDE["path"])` first in the command
(`demetra/services/agents/claude.py:407`); the test asserted `command[0].endswith("claude")`, true only for the
default `~/.local/bin/claude`. Claude Code's versioned install layout names the binary after the version.

**Fix.** **File:** `tests/test_claude.py:379`

```python
from demetra.settings import BASE_PATH, CLAUDE, UV
...
assert command[0] == str(CLAUDE["path"])
```

Still guards the intended behaviour (the wrapper launches the *configured* binary, not a bare `claude` from `PATH`)
without hardcoding its filename. Reproduced locally with `CLAUDE_PATH=/opt/claude/versions/2.1.285`.

## Test Results

- **default shell env** — 1102 passed
- **`AGENT_HARNESS=claude`** — before: 15 failed / 1087 passed; after: 1102 passed
- **`AGENT_HARNESS=claude ISSUE_TRACKER=clickup`** — 1102 passed
- **`CLAUDE_PATH=/opt/claude/versions/2.1.285 AGENT_HARNESS=claude`** — before: 1 failed; after: 1102 passed
- **`uv run ruff check .` / `ruff format --check` / `uv run ty check`** — clean
- **`uv run pre-commit run --files <changed>`** — all hooks passed

Pre-existing, unrelated noise: `tests/test_auth_password_api.py` teardown logs two SQLAlchemy `RuntimeError: Event loop
is closed` / "attached to a different loop" tracebacks at ERROR level while closing an asyncpg connection from a
different event loop than the one that opened it. No test fails; reproduces with all of this session's changes stashed.

---

## Follow-ups

- Fix the asyncpg "different loop" teardown noise in the async DB fixture used by `tests/test_auth_password_api.py`
  (cosmetic, but it hides real errors in CI logs).
- `tests/test_tracker.py` still pins `ISSUE_TRACKER` per-test via `patch("demetra.settings.ISSUE_TRACKER", ...)`; those
  patches are now redundant with `pin_default_backends` and could be removed.
- Consider a second pin for `CLAUDE["path"]`-style host paths if more tests start asserting on binary locations.

## References

- Related: [[2026-09-16-mnt-205-revise-merged-environment]] — introduced `SessionEnvironment` and the original
  `_settings_default` fallback layer
- Related: [[2026-09-30-mnt-230-claude-code-harness]] — `AGENT_HARNESS` and `tests/test_harness.py`
- Related: [[2026-09-30-clickup-issue-tracker-support]] — `ISSUE_TRACKER` and the ad hoc pin in `tests/test_tracker.py`
- Related: [[2026-09-30-langsmith-subprocess-env]] — last page to extend `_settings_default` before the move
