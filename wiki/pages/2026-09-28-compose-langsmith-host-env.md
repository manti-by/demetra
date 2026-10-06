---
title: Forward LangSmith env vars from host to containers
date: 2026-09-28
type: implementation
status: resolved
session_id: ses_f18b1bf6dffeluPnstTNqJ32iq
services: [deploy]
branch: master
tickets: []
tags: [docker, compose, langsmith, opencode, env, tests]
related:
- 2026-08-18-compose-anchors-refactor.md
- 2026-08-10-docker-compose-deploy.md
- 2026-08-17-docker-setup-review.md
- 2026-08-20-fix-allowlist-tests.md
- 2026-08-06-allowlist-review-fixes.md
- 2026-07-23-agents-md-revalidation-and-docs-removal.md
- 2026-10-06-unify-subprocess-env-on-session-environment.md
---

# Forward LangSmith env vars from host to containers

## TL;DR

`docker-compose.yaml` now forwards four LangSmith variables into every demetra
container via the existing `x-demetra-env` anchor, using host interpolation
(`${VAR:-default}`) so exporting them in the shell that runs `make deploy` /
`make docker-up` is enough — the shell outranks `--env-file .env.docker` for
interpolation. Backed by a new `tests/test_docker_compose.py` (4 tests,
mutation-verified). Two gaps remain open: the vars are dropped before `opencode`
starts by `OS_ENV_ALLOWLIST`, and the plugin never reads `LANGSMITH_TRACING`, so
tracing does not actually turn on yet.

---

## Overview

The LangSmith plugin `@langchain/langsmith-opencode` was registered in
`opencode.json` back in [[2026-07-23-agents-md-revalidation-and-docs-removal]],
but the app containers had no way to receive a LangSmith key. `.env.docker`
feeds every service through `env_file:`, which covers app secrets — yet a
developer key living in the host shell or in a secret manager is not in that
file, so there was no path from host → container.

Adding a fourth variable to `env_file` was rejected in favour of `${VAR:-}`
interpolation, which reads the host shell first and falls back to
`--env-file`/`.env`. It needs no change to `settings.py` and no secret ever
enters git.

**File:** `docker-compose.yaml:3-11`

Before:

```yaml
x-demetra-env: &demetra-env
  DB_HOST: postgres
  REDIS_URL: redis://redis:6379/1
```

After:

```yaml
x-demetra-env: &demetra-env
  DB_HOST: postgres
  REDIS_URL: redis://redis:6379/1
  LANGSMITH_TRACING: "${LANGSMITH_TRACING:-true}"
  LANGSMITH_ENDPOINT: "${LANGSMITH_ENDPOINT:-https://api.smith.langchain.com}"
  LANGSMITH_API_KEY: "${LANGSMITH_API_KEY:-}"
  LANGSMITH_PROJECT: "${LANGSMITH_PROJECT:-Demetra}"
```

The anchor chosen is the one introduced by
[[2026-08-18-compose-anchors-refactor]]: it is already merged into the
`environment:` block of all six services (`migrate`, `api`, `worker`,
`watcher`, `listener`, `rq-dashboard`), so this is the single place to add an
app-wide variable. An `environment:` block on `x-demetra-app` would have been
dead config — every app service defines its own `environment:`, which shadows
the anchor-level key.

**Zero new secret exposure:** all six services already load `env_file:
.env.docker` via `x-demetra-base`, so no service sees a secret it did not
already have.

### Why `:-` and not bare `${VAR}`

`${VAR}` with an unset host value makes compose emit a
`variable is not set. Defaulting to a blank string` warning on every
`make docker-*` invocation. `${VAR:-}` degrades silently to an empty string,
which the LangSmith plugin treats as "not configured". Verified both ways with
`docker compose --env-file .env.docker config`.

## Step 1 — Document the contract in `.env.docker.example`

**File:** `.env.docker.example:46-51`

The vars are listed as uncommented `KEY=value` lines with the intended
defaults, documenting what compose falls back to. `LANGSMITH_API_KEY` is left
empty on purpose — the key never belongs in a committed file.

## Step 2 — Lock it in with tests

**File:** `tests/test_docker_compose.py` (new, 49 lines, 4 tests)

Config assertions on `docker-compose.yaml` via `yaml.safe_load` (PyYAML is
already a core dependency). PyYAML resolves `<<` merge keys, so each service's
`environment` mapping is asserted *after* the anchor is folded in — that tests
real propagation rather than the anchor in isolation:

- **`test_langsmith_keys_interpolated_from_host`** — each key equals
  `${KEY:-<intended default>}`; catches a value hardcoded instead of read from
  the host, and catches an accidental default flip.
- **`test_langsmith_keys_keep_existing_env_anchor_entries`** — `DB_HOST` /
  `REDIS_URL` untouched by this change.
- **`test_opencode_services_merge_the_env_anchor`** — `api`, `worker`,
  `watcher`, `listener` (the opencode-spawning services) each carry the four
  interpolated values.

The expectations live in a `LANGSMITH_ENV_DEFAULTS` mapping rather than being
mirrored from the file, so the test states intent instead of tautology.

## Step 3 — Tests went red after the compose vars were revised

The first cut forwarded the plugin's own flag, `TRACE_TO_LANGSMITH`, with
empty defaults for all four keys. The compose file was then revised to
`LANGSMITH_TRACING` with non-empty defaults, and the key list in the test was
updated to match — leaving the two assertions expecting the old uniform
`${KEY:-}` form:

```text
FAILED test_langsmith_keys_interpolated_from_host
  - assert '${LANGSMITH_TRACING:-true}' == '${LANGSMITH_TRACING:-}'
FAILED test_opencode_services_merge_the_env_anchor
```

The test was wrong, not the compose file: the revision was intentional, so per
the usual ordering the test moved to match. `LANGSMITH_ENV_DEFAULTS` +
`_expected_interpolation()` express the real invariant (each value resolves
from the host, with a specific fallback) and collapse back to `${KEY:-}` when a
default is empty. A third of the suite's value here is that it is not
vacuous — each of these mutations was applied to the compose file and each one
failed the suite, after which the file was restored:

- hardcode `LANGSMITH_PROJECT: "Demetra"` (drop the host read) → 2 failed
- delete the `LANGSMITH_ENDPOINT` line entirely → 2 failed (`KeyError`)
- flip the tracing fallback to `false` → 2 failed

## Test Results

- **`uv run pytest tests/`** — 902 passed (was 900 passed / 2 failed before Step 3)
- **`cd react && bun run test`** — 72 passed, 9 files (unaffected)
- **`uv run ruff check .`** / **`ruff format --check .`** — 204 files clean
- **`uv run ty check`** — all checks passed
- **`uv run bandit -c pyproject.toml .`** — 0 issues
- **`uv run pre-commit run --all-files`** — all hooks passed
- **`docker compose --env-file .env.docker config`** — valid; all four keys
  render for every service, with and without the host vars exported

## Open questions

Two hops stand between "the container has the key" and "traces appear in
LangSmith". Neither was in scope for this change; both are reported rather than
silently fixed, since `OS_ENV_ALLOWLIST` is a deliberate security boundary.

### Gap 1 — `OS_ENV_ALLOWLIST` drops the key before `opencode` starts

**File:** `demetra/services/runtime/subprocess.py:12-28`

```python
allowed_keys = set(OS_ENV_ALLOWLIST)
if project_id is not None:
    allowed_keys.update(OS_ENV_PROJECT_OPTINS.get(project_id, []))
return {key: value for key, value in os.environ.items() if key in allowed_keys}
```

`run_command` builds every subprocess environment through
`build_subprocess_env` (`subprocess.py:122,192`), so demetra's spawn of the
`opencode` CLI inherits only the allowlist at
`demetra/library/constants.py:32-63` plus per-project opt-ins. No
`LANGSMITH_*` key is in it, so the container environment is correct but the
plugin still sees nothing.

Options: add `LANGSMITH_API_KEY` / `LANGSMITH_TRACING` to `OS_ENV_ALLOWLIST`,
or opt them in per project via `OS_ENV_PROJECT_OPTINS`. Either needs a test
alongside the existing allowlist assertions in `tests/test_settings.py:224`
(see also [[2026-08-20-fix-allowlist-tests]] and
[[2026-08-06-allowlist-review-fixes]] for that gate's history).

### Gap 2 — the plugin ignores `LANGSMITH_TRACING`

From the plugin's `src/config.ts` (`getEnvConfig`):

```ts
const enabled = process.env.TRACE_TO_LANGSMITH;
enabled: enabled == null ? undefined : enabled === "true",
```

The enable flag is read **only** from `TRACE_TO_LANGSMITH`; `LANGSMITH_TRACING`
is never referenced, so the forwarded `LANGSMITH_TRACING: "${...:-true}"` does
not switch the plugin on and `enabled` stays `false`. The other three keys are
read correctly through the `getVar()` fallbacks — `API_KEY`, `ENDPOINT`,
`PROJECT` map to `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`,
`LANGSMITH_PROJECT`.

The only non-env way to enable it is an `.opencode/langsmith.json` with
`enabled: true`, which the repo does not contain. This is a one-line compose
change plus a matching test default.

> **Consistency note (2026-10-06, Consistency Agent):** both gaps are closed by
> [[2026-10-06-unify-subprocess-env-on-session-environment]] —
> `SessionEnvironment.system_env` (`demetra/library/models.py:482`) emits both
> `LANGSMITH_TRACING` and `TRACE_TO_LANGSMITH` (plus key/endpoint/project), and
> `build_subprocess_env` merges `environment.subprocess_env` *after*
> `filter_os_env`, so the derived vars bypass `OS_ENV_ALLOWLIST`. "Tracing does
> not turn on yet" above is stale; the remaining concern is the follow-up on
> that page (unconditional `LANGSMITH_API_KEY` emission widening the credential
> surface).

## Follow-ups

- Decide on Gap 1 (`OS_ENV_ALLOWLIST` vs `OS_ENV_PROJECT_OPTINS`) and Gap 2
  (`TRACE_TO_LANGSMITH`) together — neither alone is sufficient, both are needed
  for end-to-end tracing.
- Ruled out while working: an `environment:` entry on `x-demetra-app` (shadowed
  by each service's own block); a `settings.py` constant (the plugin reads the
  OS env directly, no Python layer involved); reading the key from
  `.env.docker` via `env_file` alone (works, but forces the key into a file the
  developer is expected to keep untracked per service).

## References

- Related: [[2026-08-18-compose-anchors-refactor]]
- Related: [[2026-08-10-docker-compose-deploy]]
- Related: [[2026-08-17-docker-setup-review]]
- Related: [[2026-08-20-fix-allowlist-tests]]
- Related: [[2026-08-06-allowlist-review-fixes]]
- Related: [[2026-07-23-agents-md-revalidation-and-docs-removal]]
- Related: [[2026-10-06-unify-subprocess-env-on-session-environment]]
- External: [@langchain/langsmith-opencode](https://github.com/langchain-ai/langsmith-opencode)
