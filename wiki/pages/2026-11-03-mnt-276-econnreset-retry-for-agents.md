---
title: 'MNT-276: ECONNRESET retry for agents'
date: '2026-11-03'
type: implementation
status: resolved
session_id: ses_e5ed4a18cffeuswBCPXVvJ69Jx
services: [agents, workflows, runtime, templates, settings, library, main]
branch: mnt-276-econnreset-retry-for-agents
tickets: [MNT-276]
tags: [wiki, feature, backend]
related: [2026-07-21-rich-markuperror-and-run-attempts.md, 2026-08-19-build-agent-server-error-handler.md]
---

# MNT-276: ECONNRESET retry for agents

## TL;DR

`opencode` runs that die on a transient network error (`ECONNRESET`, `socket hang up`,
`ETIMEDOUT`, …) previously failed the whole workflow on the first attempt. `run_opencode_agent` now
retries those runs with exponential backoff up to `MAX_AGENT_NETWORK_ATTEMPTS` (default 5) and, when
the budget is exhausted, raises `AgentNetworkError`; `main.py` catches it, posts the new
`agent_network_failed` Linear comment with the last stderr, and moves the ticket to `Awaiting Input`
without marking it failed.

## Overview

The change is a retry budget around the single shared runner plus a typed terminal error, so the six
agent wrappers that opt in get identical behaviour and the failure handler can render a specific
comment instead of the generic `DemetraError` path.

## Step 1 — Typed error

**File:** `demetra/library/exceptions.py:69`

```python
class AgentNetworkError(DemetraError):
    def __init__(self, agent: str, stderr: str) -> None:
        super().__init__(f"Agent '{agent}' failed with a network error: {stderr.strip() or 'unknown error'}")
        self.agent = agent
        self.stderr = stderr
```

It carries the agent name and the last captured stderr so the failure template has real context.

## Step 2 — Transient-error detection

**File:** `demetra/services/agents/opencode.py:31` (markers) and `:313` (`is_network_error`)

```python
NETWORK_ERROR_MARKERS = (
    "ECONNRESET",
    "ECONNREFUSED",
    "ETIMEDOUT",
    "ENOTFOUND",
    "EAI_AGAIN",
    "socket hang up",
)
```

Only stderr and the structured `--format json` error event on stdout are scanned — stdout also
carries the agent's own answer, so scanning it raw would treat a mention of an error code as a
dropped connection.

## Step 3 — Retry loop in `run_opencode_agent`

**File:** `demetra/services/agents/opencode.py:644` (`run_opencode_agent`), loop at `:693`

```python
attempts = max(MAX_AGENT_NETWORK_ATTEMPTS, 1) if retry_on_network_error else 1
resumed_session_id: str | None = None
for attempt in range(attempts):
    ...
    retryable = retry_on_network_error and exit_code != 0 and is_network_error(stdout=stdout, stderr=stderr)
    if not retryable:
        return exit_code, stdout, stderr
    ...
    delay = AGENT_NETWORK_BACKOFF_BASE * 2**attempt
```

`MAX_AGENT_NETWORK_ATTEMPTS` defaults to 5 and `AGENT_NETWORK_BACKOFF_BASE` to 1.0s
(`demetra/settings.py:61-62`), so delays double per attempt. After the first failed attempt the
runner resolves the session id it just created (or forked) and resumes **that** session instead of
re-sending the prompt to the parent; if a `--fork`ed session cannot be located it stops retrying
rather than falling back to the parent session.

The six wrappers that pass `retry_on_network_error=True` are plan, build, review, validate, resolve
and research (`:371`, `:409`, `:443`, `:479`, `:605`, `:640`). Merge, rebase and review-fixes keep
the default `False`, so those runs fail fast.

## Step 4 — Terminal error

**File:** `demetra/services/agents/opencode.py:745`

When every attempt is retryable the runner raises
`AgentNetworkError(agent=agent, stderr=stderr.strip() or _extract_ndjson_error(stdout) or "")`.

## Step 5 — Failure handler

**File:** `main.py:214`

```python
except AgentNetworkError as e:
    await process_agent_network_failure(context=context, error=e)
    failure_step, should_update_linear_status = "awaiting_input", False
    failure_message = str(e) or None
```

`process_agent_network_failure` (`demetra/workflows/failure.py:100`) renders
`demetra/templates/agent_network_failed.md` with `{agent_name}`/`{error}`, posts it as an
`agent-network-failure` comment and moves the ticket to `Awaiting Input`. Setting
`should_update_linear_status = False` keeps the generic failure path from overwriting that state:
the run stops for recovery, it does not mark the ticket failed.

## Step 6 — Tests

- `tests/test_opencode.py:180` `TestAgentNetworkRetry` — marker detection (stdout mentions ignored,
  stderr and NDJSON error events matched), success without retry, retry-then-succeed, exhausted
  budget raising `AgentNetworkError`, backoff sleeps.
- `tests/test_failure.py:130` — `process_agent_network_failure` renders the template with the agent
  name and stderr and moves the ticket to `Awaiting Input`.
- `tests/test_entrypoints.py:278` — `main()` routes `AgentNetworkError` to
  `process_agent_network_failure` and records `awaiting_input`.

## Test Results

Full suite green: `273 passed` across the affected workflow/agent/subprocess/entrypoint test
modules after the merge; `ruff`, `ty` and `bandit` clean.

## Follow-ups

- None

## References

- Related: [[2026-07-21-rich-markuperror-and-run-attempts]] — earlier agent-failure handling where a
  crash consumed the run budget and the workflow died with empty stderr
- Related: [[2026-08-19-build-agent-server-error-handler]] — the generic `UnknownError` →
  `Awaiting Input` handler this specialised path complements
- External: https://linear.app/mnt/issue/MNT-276/econnreset-retry-for-agents
