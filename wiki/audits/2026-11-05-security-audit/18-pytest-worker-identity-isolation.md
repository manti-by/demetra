# 18 — Pytest runs repository code with worker identity

## Summary

- **Title:** Repository test code executes with the orchestration worker's authority
- **Problem:** When pytest is enabled, the workflow executes project repository code
  (`conftest.py`, test modules) with the orchestration worker's identity and filesystem
  access via `run_command` (`uv run --active pytest`). A project owner can place
  executable test code in their repository and thereby reach shared operator
  credentials or other projects their application account cannot access.
- **Date:** 2026-11-05
- **Severity:** medium · **Category:** security_misconfiguration
- **CodeRabbit ID:** `135414d0-82bd-4caf-99e2-bc3058a34b3a`
- **Files (current):** `demetra/services/runtime/subprocess.py:93-138`
  (`run_command`), `demetra/services/quality/test.py`, `demetra/workflows/lint.py`
- **Revalidation:** Confirmed. `run_command` runs repository commands with the worker's
  merged environment (including project credentials) and no identity or filesystem
  boundary. Mitigation today is the `IS_PYTEST_ENABLED` flag defaulting to `False`.

## Steps

1. Execute project tests in an isolated container (or a dedicated unprivileged
   identity) containing only that project's checkout and the minimum required
   credentials, mirroring the Compose worker layout.
2. Keep operator credentials, orchestration files, and other projects' storage outside
   the test execution boundary (no shared home, no `LANGSMITH_API_KEY`, no `.keys/*`
   mounts inside the test sandbox).
3. Until isolation lands, keep `IS_PYTEST_ENABLED=False` by default and require an
   explicit per-project opt-in that uses a dedicated, non-operator credential.
4. Combine with plans 03 and 05 so the test sandbox also strips operator secrets and
   tenant-controlled `GIT_*`/`SSH_*` overrides.
5. Add a guardrail test/CI check that the pytest subprocess environment and working
   directory exclude operator-only resources.
