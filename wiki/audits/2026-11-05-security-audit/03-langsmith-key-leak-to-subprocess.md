# 03 — LangSmith API key leaked into repository subprocess environment

## Summary

- **Title:** Operator's `LANGSMITH_API_KEY` reaches repository-controlled test code
- **Problem:** `SessionEnvironment.system_env` resolves `LANGSMITH_API_KEY` through
  the layered lookup and, when neither project nor user provides a key, falls back to
  the operator's private platform credential — regardless of whether tracing is
  enabled. These derived tracing vars are merged into `subprocess_env`, which
  `build_subprocess_env` forwards to every general subprocess, including the
  repository-controlled `pytest` run.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-200** · **Category:** sensitive_data_exposure
- **CodeRabbit ID:** `b839f136-385f-4cf5-8c5c-8f1d1da91018`
- **Files (current):** `demetra/library/models.py:607-629` (`system_env`),
  `demetra/services/runtime/subprocess.py:32-69` (`build_subprocess_env`)
- **Revalidation:** Confirmed. `system_env` still returns `LANGSMITH_API_KEY`, and the
  `build_subprocess_env` docstring confirms derived tracing vars are always present in
  `subprocess_env` and forwarded to repository commands.

## Steps

1. Split tracing configuration from secrets: keep `LANGSMITH_TRACING` /
   `TRACE_TO_LANGSMITH` booleans (and non-secret `LANGSMITH_ENDPOINT` /
   `LANGSMITH_PROJECT`) for subprocesses, but stop returning `LANGSMITH_API_KEY` from
   `system_env` for the general subprocess path.
2. In `build_subprocess_env`, strip `LANGSMITH_API_KEY` (and any other operator-secret
   key) from `merged_env` unless the command is an explicit trusted tracing invocation.
3. Provide the API key only to the trusted tracing component (the OpenCode/agent
   subprocess wrapper), or via explicitly project-scoped credentials
   (`OS_ENV_PROJECT_OPTINS`), never via the operator fallback.
4. Add a test asserting `build_subprocess_env(...)` for a repository test does **not**
   contain `LANGSMITH_API_KEY`.
