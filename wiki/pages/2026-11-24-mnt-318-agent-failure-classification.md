---
title: 'MNT-318: Classify agent failures into typed Demetra errors'
generated: {by: demetra, at: '2026-11-24T00:00:00Z'}
description: Implemented a classifier for OpenCode agent failures with typed exceptions, redaction, and consistent error handling across workflows, passing all tests and enabling readable Linear comments and proper ticket routing.
type: implementation
status: stable
session_id: ses_df2caf592ffeXFuVo9jwwBksJS
services: [.env.docker, library, agents/opencode, settings, templates, workflows, main, pyproject, test_entrypoints, test_failure, test_opencode, test_workflows, uv, INDEX, 2026-11-24-mnt-318-agent-failure-classification]
branch: mnt-318-classify-agent-failures-into-typed-demetra-errors
tickets: [MNT-318]
tags: [wiki, feature]
related: [2026-11-03-mnt-276-econnreset-retry-for-agents.md, 2026-08-19-build-agent-server-error-handler.md, 2026-11-06-mnt-298-research-econnreset-root-cause.md]
---

# MNT-318: Classify agent failures into typed Demetra errors

## TL;DR

This session implemented a classifier for OpenCode agent failures, mapping them to specific error types like quota exhaustion, rate limits, and context overflows. The changes introduce typed exceptions, redaction of sensitive information, and consistent error handling across plan, build, validate, and research steps. All tests passed, ensuring classified errors produce readable Linear comments and move tickets to Awaiting Input when appropriate.

## Overview

The implementation introduces a central error classifier that maps agent failure output to specific error types. This includes adding typed exceptions, redacting sensitive information, and updating error handling across all agent workflows. The goal is to provide clear, actionable error messages and ensure consistent behavior across different agent steps.

## Step 1 — Add error classes and constants

**File:** `demetra/library/exceptions.py`

Added a base `AgentFailureError` class and seven subclasses for specific error types:

```python
class AgentFailureError(DemetraError):
    def __init__(self, agent: str, stderr: str, code: str, retry_after_ms: int | None = None):
        self.agent = agent
        self.stderr = stderr
        self.code = code
        self.retry_after_ms = retry_after_ms
        self.template = f"agent_{code}_failed.md"
        self.retryable = code in RETRYABLE_CODES
```

**File:** `demetra/library/constants.py`

Added signature mappings for error classification:

```python
AGENT_FAILURE_SIGNATURES: tuple[tuple[str, tuple[str, ...], type[AgentFailureError], bool], ...] = (
    ("budget_retry", ("requires more credits", "can only afford"), AgentBudgetRetryError, True),
    ("quota_exhausted", ("insufficient credits", "credits exhausted"), AgentQuotaError, False),
    ("rate_limited", ("RATE_LIMIT", "rate limit exceeded"), AgentRateLimitError, True),
    ...
)
```

## Step 2 — Implement classification and redaction

**File:** `demetra/services/agents/opencode.py`

Added `classify_agent_error` to map stderr to error types:

```python
def classify_agent_error(stdout: str, stderr: str) -> AgentFailure | None:
    for code, markers, exc_cls, retryable in AGENT_FAILURE_SIGNATURES:
        if any(marker in stderr for marker in markers):
            return AgentFailure(code=code, exc_cls=exc_cls, retryable=retryable)
    return None
```

Added `redact_provider_text` to sanitize sensitive information:

```python
def redact_provider_text(text: str) -> str:
    return re.sub(r"https://[^\s]+", "[REDACTED]", text)
```

## Step 3 — Update workflow steps

**File:** `demetra/workflows/plan.py`

Replaced generic error handling with classified errors:

```python
raise agent_failure_error(
    agent="plan",
    exit_code=exit_code,
    stdout=stdout,
    stderr=stderr,
    fallback=PlanError,
)
```

Similar changes were made to `build.py`, `validate.py`, and `research.py`.

## Step 4 — Add failure processing

**File:** `demetra/workflows/failure.py`

Added `process_agent_failure` to handle error rendering:

```python
def process_agent_failure(error: AgentFailureError, context: Context) -> None:
    body = render_template(error.template, agent_name=error.agent, error=error.stderr)
    notify_linear_failure(context=context, body=body, comment_label="agent-failure")
```

## Test Results

All 1647 tests passed, including new tests for classification, redaction, and error handling:

```
============================ 1647 passed in 39.09s ============================
```

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-318/classify-agent-failures-into-typed-demetra-errors
- Related: [2026-11-03-mnt-276-econnreset-retry-for-agents](/pages/2026-11-03-mnt-276-econnreset-retry-for-agents.md)
- Related: [2026-08-19-build-agent-server-error-handler](/pages/2026-08-19-build-agent-server-error-handler.md)
- Related: [2026-11-06-mnt-298-research-econnreset-root-cause](/pages/2026-11-06-mnt-298-research-econnreset-root-cause.md)
