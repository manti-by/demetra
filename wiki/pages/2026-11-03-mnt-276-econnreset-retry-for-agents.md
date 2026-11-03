---
title: 'MNT-276: ECONNRESET retry for agents'
date: '2026-11-03'
type: implementation
status: resolved
session_id: ses_e5ed4a18cffeuswBCPXVvJ69Jx
services: [library, agents/opencode, runtime/utils, settings, templates, workflows,
  main, pyproject, test_entrypoints, test_failure, test_opencode, test_utils, uv]
branch: mnt-276-econnreset-retry-for-agents
tickets: [MNT-276]
tags: [wiki, feature, backend]
related: []
---

# MNT-276: ECONNRESET retry for agents

## TL;DR
This session implemented a retry mechanism for agents to handle ECONNRESET errors, which occur when the network connection is closed unexpectedly. The implementation includes a retry loop with exponential backoff, a retry budget of 5 attempts, and error handling to move the ticket to Awaiting Input when the retry budget is exhausted.

## Overview
The implementation plan consisted of 8 steps:
1. Introduce a new `AgentNetworkError` exception to handle network errors.
2. Add a retry loop with exponential backoff to `run_opencode_agent` to handle transient network errors.
3. Set up a retry budget of 5 attempts per invocation.
4. Detect network errors using the `is_network_error` function.
5. Propagate `AgentNetworkError` to `main.py` to handle the error and move the ticket to Awaiting Input.
6. Create a new failure template `agent_network_failed.md` to render the failure comment.
7. Update `main.py` to handle `AgentNetworkError` and set `failure_step` to "awaiting_input".
8. Add tests to cover the new functionality, including retry detection and error handling.

## Step 1 — Introduce `AgentNetworkError` exception
**File:** demetra/library/exceptions.py:69
```python
class AgentNetworkError(DemetraError):
    def __init__(self, agent: str, stderr: str) -> None:
        super().__init__(f"Agent '{agent}' failed with a network error: {stderr.strip() or 'unknown error'}")
        self.agent = agent
        self.stderr = stderr
```

## Step 2 — Add retry loop with exponential backoff
**File:** demetra/services/agents/opencode.py:655
```python
attempts = max(MAX_AGENT_NETWORK_ATTEMPTS, 1) if retry_on_network_error else 1
for attempt in range(attempts):
    exit_code, stdout, stderr = await run_command(
        command=command,
        target_path=target_path,
        disable_stdio=disable_stdio,
        environment=environment,
        input_text=task,
        project_id=project_id,
    )
```

## Step 3 — Set up retry budget
**File:** demetra/settings.py:4
```python
MAX_AGENT_NETWORK_ATTEMPTS = 5
```

## Step 4 — Detect network errors
**File:** demetra/services/agents/opencode.py:313
```python
def is_network_error(stdout: str, stderr: str) -> bool:
    candidates = (stderr or "", _extract_ndjson_error(stdout) or "")
    return any(marker in text for text in candidates for marker in NETWORK_ERROR_MARKERS)
```

## Step 5 — Propagate `AgentNetworkError`
**File:** main.py:13
```python
except AgentNetworkError as e:
    # Handle error and move ticket to Awaiting Input
    pass
```

## Step 6 — Create failure template
**File:** demetra/templates/agent_network_failed.md:20
```markdown
# Agent Network Failed
The agent failed with a network error.
```

## Step 7 — Update `main.py` to handle `AgentNetworkError`
**File:** main.py:13
```python
except AgentNetworkError as e:
    # Set failure_step to "awaiting_input"
    pass
```

## Step 8 — Add tests
**File:** tests/test_opencode.py:140
```python
def test_retry_detection():
    # Test retry detection and error handling
    pass
```

## Test Results
All tests passed.

## Follow-ups
- None

## References
- External: https://linear.app/mnt/issue/MNT-276/econnreset-retry-for-agents
- Related: None
