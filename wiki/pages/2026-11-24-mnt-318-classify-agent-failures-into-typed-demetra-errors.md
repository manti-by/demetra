---
title: 'MNT-318: Classify agent failures into typed Demetra errors'
generated: {by: demetra, at: '2026-11-25T00:00:00Z'}
description: Implemented a classifier for OpenCode agent failures that maps them to typed Demetra errors with dedicated handlers, templates and workflow states, properly handling quota exhaustion, rate limits and permission errors while redacting sensitive information.
type: implementation
status: stable
session_id: ses_df2caf592ffeXFuVo9jwwBksJS
services: [.env.docker, library, agents/opencode, settings, templates, workflows, main, pyproject, test_entrypoints, test_failure, test_opencode, test_workflows, uv, INDEX]
branch: mnt-318-classify-agent-failures-into-typed-demetra-errors
tickets: [MNT-318]
tags: [wiki, feature]
related: [2026-11-03-mnt-276-econnreset-retry-for-agents.md, 2026-08-19-build-agent-server-error-handler.md, 2026-11-06-mnt-298-research-econnreset-root-cause.md]
---

# MNT-318: Classify agent failures into typed Demetra errors

## TL;DR

Implemented a classifier for OpenCode agent failures that maps them to typed Demetra errors with dedicated handlers, templates and workflow states. The system now properly handles and distinguishes between quota exhaustion, rate limits, permission errors and other common failure modes, providing clear user-facing messages while redacting sensitive information. All agent steps (plan, build, validate, research) now flow through the same classification mechanism, so classified errors produce readable Linear comments and move the ticket to Awaiting Input when appropriate. All tests passed.

## Overview

This change introduces a runtime classifier that maps agent failure output onto typed exceptions with dedicated Markdown templates and handlers, similar to the existing transport error mechanism. Key components:

1. **Error hierarchy** - New `AgentFailureError` base class with 7 subclasses for specific error types
2. **Signature matching** - Central mapping of error patterns to exception types and retry behavior
3. **Redaction** - Sensitive information removal from error messages
4. **Workflow integration** - Unified handling across all agent steps
5. **Templates** - User-friendly messages for each error type

## Step 1 — Error classes and constants

**File:** `demetra/library/constants.py`

Added error signature mapping and type codes:

```python
AGENT_FAILURE_SIGNATURES: tuple[tuple[str, tuple[str, ...], type[AgentFailureError], bool], ...] = (
    (
        "budget_retry",
        ("requires more credits", "can only afford", "reduce max_tokens", "retry with fewer tokens"),
        AgentBudgetRetryError,
        True,
    ),
    # ... other signatures ...
)
```

**File:** `demetra/library/exceptions.py`

Added a base class and subclasses carrying the error code, redacted stderr and retry metadata. Both earlier write-ups of this session showed a constructor taking `template`/`retryable` directly; the verified current class (`demetra/library/exceptions.py:81`) keeps those as class-level defaults and accepts an optional `code` override:

```python
class AgentFailureError(DemetraError):
    code = "agent_failure"
    template = "agent_provider_failed"
    retryable = False

    def __init__(self, agent: str, stderr: str, *, code: str | None = None, retry_after_ms: int | None = None) -> None:
        self.agent = agent
        self.stderr = stderr
        self.code = code or type(self).code
        self.retry_after_ms = retry_after_ms
```

## Step 2 — Classification and redaction

**File:** `demetra/services/agents/opencode.py`

`classify_agent_error` scans provider stderr for the signature markers and returns the matching failure class and retry behaviour:

```python
def classify_agent_error(stdout: str, stderr: str) -> AgentFailure | None:
    for code, markers, exc_cls, retryable in AGENT_FAILURE_SIGNATURES:
        if any(marker in stderr for marker in markers):
            return AgentFailure(code=code, exc_cls=exc_cls, retryable=retryable)
    return None
```

`redact_provider_text` removes credentials from provider output before it reaches a human — billing or key-management URLs, Authorization headers, quoted credential fields, URL user info and the key itself:

```python
def redact_provider_text(text: str) -> str:
    redacted = _SENSITIVE_URL_RE.sub("[redacted-url]", text or "")
    redacted = _URL_USERINFO_RE.sub(r"\1[redacted]@", redacted)
    return _CREDENTIAL_FIELD_RE.sub(r"\1\2[redacted]\4", redacted)
```

## Step 3 — Workflow integration

**File:** `main.py`

The top-level handler recognises classified failures without failing the ticket:

```python
except AgentFailureError as e:
    failure_step = "awaiting_input"
    should_update_linear_status = False
    process_agent_failure(context, e)
```

**File:** `demetra/workflows/failure.py`

```python
def process_agent_failure(context: Context, error: AgentFailureError) -> None:
    body = render_template(
        error.template,
        agent_name=error.agent,
        error=error.stderr,
        code=error.code,
        retry_after=(
            f"Retry after {error.retry_after_ms // 1000}s"
            if error.retry_after_ms
            else ""
        ),
    )
    notify_linear_failure(
        context=context,
        body=body,
        comment_label="agent-failure",
    )
```

**Files:** `demetra/workflows/plan.py`, `build.py`, `validate.py`, `research.py`

Generic error handling in each agent step was replaced with the classified path, e.g.:

```python
raise agent_failure_error(
    agent="plan",
    exit_code=exit_code,
    stdout=stdout,
    stderr=stderr,
    fallback=PlanError,
)
```

## Test Results

- 188 focused tests passed
- Full test suite: 1669 passed (an earlier run in the session recorded 1647 passed)
- Linting and type checks clean
- Verified all error types are properly classified and rendered
- Confirmed sensitive information is redacted
- Validated workflow state transitions

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-318/classify-agent-failures-into-typed-demetra-errors
- Related: [2026-11-03-mnt-276-econnreset-retry-for-agents](/pages/2026-11-03-mnt-276-econnreset-retry-for-agents.md)
- Related: [2026-08-19-build-agent-server-error-handler](/pages/2026-08-19-build-agent-server-error-handler.md)
- Related: [2026-11-06-mnt-298-research-econnreset-root-cause](/pages/2026-11-06-mnt-298-research-econnreset-root-cause.md)
