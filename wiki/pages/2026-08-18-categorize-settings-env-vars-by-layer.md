---
title: Categorize settings env vars by layer
date: 2026-08-18
type: investigation
status: resolved
session_id: "-"
services: [settings, subprocess, workflows, persistence]
branch: feature/mnt-169-removeupdate-settings
tickets: [MNT-169, MNT-170]
tags: [environment, settings, project-env, user-env, layers, subprocess]
related: [2026-06-08-project-environment.md, 2026-07-23-session-tokens-audit-revalidation.md, 2026-08-10-process-environment-3-layers-encryption-uv-venv.md, 2026-08-18-migrate-llm-groq-to-openrouter.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md]
---

# Categorize settings env vars by layer

## TL;DR

Classifies every workflow-runtime env var read in `demetra/settings.py` into one of three target layers — **project** (per-project `project_environment` rows), **user** (per-user `user_environment` rows where `scope = 'user'`), or **system** (kept in `settings.py`, overridable by user-shared env in the merge order OS → user-shared → project → step). The three-layer plumbing already exists per [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]; the runtime work is tracked as [MNT-170 — Migrate workflow env vars to project/user env layers](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers). Resolution from this session: one Linear workspace → OAuth + workspace labels stay system, `LINEAR_TEAM_ID` / `LINEAR_STATE_*` move to user; `OPENROUTER_BASE_URL` stays system, `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` move to user; `UV_PATH` moves to project, other tool binary paths stay system.

> **Status update (2026-08-23, Consistency Agent):** MNT-170 merged to `master` via PR #80
> (2026-08-19); see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]] for the
> follow-up service-layer refactor on the same branch. Implementation status against the
> follow-up plan below: **steps 1–4 are done** — `get_linear_config_value()` in
> `demetra/services/linear/__init__.py`, the OpenRouter user-env fallback in
> `get_openrouter_config()` (`demetra/services/llm/config.py`),
> `_resolve_opencode_model(..., user_environment=...)` in `demetra/services/agents/opencode.py`,
> and `env["UV_PATH"]` in `demetra/services/runtime/project.py:187`.
>
> **Status update (2026-08-28, Consistency Agent):** OpenCode per-agent model
> overrides from user env are now covered in `tests/test_opencode.py`
> (`TestOpencodeModelResolution`); step 5 remains partial only for
> `UV_PATH`-after-`setup_project_venv` (no test references `UV_PATH` yet).

---

## Section 1 — Project-related (per-project `project_environment` rows)

Each row flows to subprocesses via the project layer in `build_subprocess_env` (`demetra/services/runtime/subprocess.py:31`).

| Env var | Settings | Read by |
| --- | --- | --- |
| `UV_PATH` | `demetra/settings.py:155` (`UV: PathConfig["path"]`) | `demetra/services/runtime/project.py:174` (`uv venv --seed <local>/.venv`); `demetra/services/runtime/utils.py:128` (`uv tree`); joins `VIRTUAL_ENV` / `UV_PROJECT_ENVIRONMENT` already written into `project.environment` by `setup_project_venv` (`demetra/services/runtime/project.py:185-186`). |

## Section 2 — User-related (per-user `user_environment` rows, `scope = 'user'`)

Read via `get_user_environments_decrypted(user_id)` (`demetra/services/persistence/database.py:1565`) and merged into the subprocess env before the project layer (`demetra/workflows/setup.py:50-52`).

| Env var | Settings | Read by |
| --- | --- | --- |
| `LINEAR_TEAM_ID` | `demetra/settings.py:119` | `demetra/services/linear/__init__.py:283` (default team on ticket create); `demetra/services/linear/__init__.py:97` (project-name filter fallback in `get_todo_issues`). |
| `LINEAR_STATE_PRD_ID` | `demetra/settings.py:124` | `demetra/services/linear/__init__.py:131` (`default_state` lookup on the `LINEAR` config, currently the PRD uuid). |
| `LINEAR_STATE_TODO_ID` | `demetra/settings.py:125` | `demetra/services/linear/__init__.py:83` (`get_todo_issues` filter); `demetra/services/linear/__init__.py:240` (move on failure). |
| `LINEAR_STATE_IN_PROGRESS_ID` | `demetra/settings.py:126` | Reserved for an "in progress" transition (no current call site; the active 3-state loop is `todo ↔ in_review`). |
| `LINEAR_STATE_IN_REVIEW_ID` | `demetra/settings.py:127` | `demetra/services/linear/__init__.py:236` (move on success in `linear_cleanup`). |
| `LINEAR_STATE_AWAITING_INPUT_ID` | `demetra/settings.py:128` | `demetra/services/daemons/watcher.py:49,98` (move when `run_attempts` exceeds `MAX_RUN_ATTEMPTS`). |
| `LINEAR_STATE_DONE_ID` | `demetra/settings.py:129` | Reserved for a `done` transition (no current call site — workflow closes via `in_review`). |
| `LINEAR_DEFAULT_STATE_ID` | `demetra/settings.py:131` | `demetra/services/linear/__init__.py:284` (default state on ticket create). |
| `OPENROUTER_API_KEY` | `demetra/settings.py:191` | `demetra/services/llm/factory.py:25` (`ChatOpenAI(api_key=...)`); consumed indirectly by every chain in `demetra/services/llm/openrouter.py` and its callers (`workflows/plan.py`, `workflows/review.py`, `workflows/cleanup.py`, `services/wiki/__init__.py`). |
| `OPENROUTER_MODEL` | `demetra/settings.py:192` | `demetra/services/llm/factory.py:21` (`ChatOpenAI(model=...)`); same consumer chain as `OPENROUTER_API_KEY`. |
| `GROQ_API_KEY` | `demetra/settings.py:186` | Legacy `demetra/services/llm/groq.py:37,71,110,152,182,228` (`ChatGroq(api_key=...)` instances). Kept importable per the MNT-168 migration; same user-shared-env treatment for parity even though the supervisor no longer calls it directly (per [[2026-08-18-migrate-llm-groq-to-openrouter]]). |
| `GROQ_MODEL` | `demetra/settings.py:187` | Same legacy `groq.py` callers. |

## Section 3 — System keys (stay in `settings.py`, overridable by user-shared env in the merge order)

These ship as supervisor defaults; user-shared env may override at `build_subprocess_env` time (`demetra/services/runtime/subprocess.py:57-60`).

| Env var | Settings | Read by |
| --- | --- | --- |
| `OPENCODE_PATH` | `demetra/settings.py:136` | `demetra/services/agents/opencode.py:218,245,302,412` (every `opencode` invocation). |
| `OPENCODE_PLAN_MODEL` | `demetra/settings.py:137` | `demetra/services/agents/opencode.py:46` (`opencode_plan_agent`). |
| `OPENCODE_RESOLVE_MODEL` | `demetra/settings.py:138` | `demetra/services/agents/opencode.py:182` (`opencode_resolve_agent`). |
| `OPENCODE_BUILD_MODEL` | `demetra/settings.py:139` | `demetra/services/agents/opencode.py:77,157` (`opencode_build_agent`, `opencode_merge_agent`). |
| `OPENCODE_VALIDATE_MODEL` | `demetra/settings.py:140` | `demetra/services/agents/opencode.py:131` (`opencode_validate_agent`). |
| `OPENCODE_REVIEW_MODELS` | `demetra/settings.py:141` | Looped in `workflows/review.py` (one review run per model); see [[2026-07-23-session-tokens-audit-revalidation]] for call-site context. |
| `OPENROUTER_BASE_URL` | `demetra/settings.py:193` | `demetra/services/llm/factory.py:26` (`ChatOpenAI(base_url=...)`); URL validated by `validate_llm_base_url` (`demetra/services/runtime/utils.py:352`). |
| `LINEAR_CLIENT_ID` | `demetra/settings.py:116` | `demetra/services/linear/oauth.py:24,41,47` (`LinearError` guard + token-request payload). |
| `LINEAR_CLIENT_SECRET` | `demetra/settings.py:117` | `demetra/services/linear/oauth.py:24,41,48` (same OAuth flow). |
| `LINEAR_OAUTH_SCOPE` | `demetra/settings.py:118` | `demetra/services/linear/oauth.py:46` (scope form value). |
| `LINEAR_FEATURE_LABEL_ID` | `demetra/settings.py:122` | `demetra/services/linear/__init__.py:286` (label attached to created tickets). |
| `LINEAR_FILTER_LABELS` | `demetra/settings.py:132` | `demetra/services/linear/__init__.py:87,101-102` (label filter in `get_todo_issues`). |
| `GIT_PATH` | `demetra/settings.py:159` | Throughout `demetra/services/vcs/git.py` and `demetra/services/runtime/project.py:140` (clone). |
| `GIT_WORKTREE_PATH` | `demetra/settings.py:160` | `demetra/services/vcs/git.py:43` (`get_worktree_path`). |
| `GH_PATH` | `demetra/settings.py:164` | `demetra/services/vcs/github.py` (PR view/create/comment, repo clone). |
| `CURSOR_PATH` | `demetra/settings.py:147` | `demetra/services/agents/cursor.py:36`. |
| `CODERABBIT_PATH` | `demetra/settings.py:151` | `demetra/services/agents/coderabbit.py:30`. |

## Out of scope (system infrastructure, not passed to subprocesses)

These are read by the FastAPI/RQ app — DB connection, JWT signing, encryption, logging, feature flags, daemons, allowlist, daemon socket paths, HTTP/auth cookies — and do not flow through `build_subprocess_env`. They stay in `settings.py` and are listed here only to keep `grep -n 'env_get' demetra/settings.py` honest:

- App surface: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, `DB_PASSWORD`, `REDIS_URL`.
- Crypto / auth bootstrap: `SECRET_KEY`, `ENCRYPTION_SALT`, `JWT_SECRET_KEY`, `DEFAULT_USER_ID`.
- Logging: `LOG_PATH`, `LOG_LEVEL`.
- Paths: `PARENT_HOME`, `PROJECTS_PATH`.
- Workflow limits & runtime: `MAX_BUILD_ATTEMPTS`, `MAX_REVIEW_ATTEMPTS`, `MAX_MERGE_ATTEMPTS`, `MAX_REBASE_ATTEMPTS`, `MAX_PLAN_ATTEMPTS`, `MAX_RUN_ATTEMPTS`, `MAX_LISTENER_ATTEMPTS`, `SUBPROCESS_TIMEOUT`, `CONTEXT_COMPACTION_THRESHOLD`.
- Feature flags / wiki tuning: `IS_RUFF_ENABLED`, `IS_PYTEST_ENABLED`; `WIKI_LLM_BUDGET_FILES`, `WIKI_LLM_BUDGET_LINES`, `WIKI_DIFF_HUNK_CAP`, `WIKI_BUILD_PLAN_CAP`, `WIKI_REVALIDATION_ENABLED`.
- Daemons & allowlist: `WATCHER_POLL_INTERVAL`, `LISTENER_POLL_INTERVAL`; `IS_ALLOWLIST_ENABLED`, `ALLOWLIST_SEED_FILE`.
- Env-layer config: `OS_ENV_PROJECT_OPTINS`, `OS_ENV_ALLOWLIST`.
- Web/auth cookies: `COOKIE_SECURE`, `COOKIE_SAMESITE`, `CORS_ALLOWED_ORIGINS`.
- Debug: `DEBUG`.

---

<!--
  IMPLEMENTATION PLAN — FOLLOW-UP MIGRATION. The 5 steps below are tracked as
  [MNT-170 — Migrate workflow env vars to project/user env layers](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers)
  (state: Todo, assignee: demetra.ai, parent: MNT-169). MNT-161's 3-layer plumbing
  already merges per-user + per-project + step on top of the OS allowlist, so the
  only work is wiring the fallback chain in settings.py callers.
-->
## Follow-up migration plan (executed by MNT-170)

The blocks below enumerate the changes [MNT-170](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers) will touch. See that ticket for the full implementation plan including code snippets, tests, and acceptance criteria.

1. **Linear states + team (`LINEAR_TEAM_ID`, `LINEAR_STATE_*_ID`, `LINEAR_DEFAULT_STATE_ID`) → user-shared env.** Each `LINEAR[...]` lookup in `demetra/services/linear/__init__.py:83,236,240,283-284` and `demetra/services/daemons/watcher.py:49,98` is replaced with a small resolver `get_linear_state(name, *, user_id) -> str` that reads `user_environment[name]` first, then falls back to `settings.LINEAR[...]`. `setup_workflow` (`demetra/workflows/setup.py:46-52`) already loads both layers; thread the resolved dict down via `Context` or pass `user_environment` into the resolver. A one-time migration seeds the user-shared env rows for existing users from the current `settings.LINEAR` defaults.
2. **OpenRouter user overrides (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`).** Change `demetra/services/llm/factory.py:21,25` to a fallback chain: `user_environment.get("OPENROUTER_API_KEY") or settings.OPENROUTER["api_key"]` (same for `OPENROUTER_MODEL`). `OPENROUTER_BASE_URL` stays in `settings.py` per the task spec; thread a `user_environment` kwarg into `build_llm(...)` and propagate it from the four LLM-consumer call sites (`workflows/plan.py`, `workflows/review.py`, `workflows/cleanup.py`, `services/wiki/__init__.py`).
3. **OpenCode user overrides (`OPENCODE_*_MODEL`).** Thread an optional `user_environment: dict[str,str] | None` parameter into every `opencode_*_agent` helper in `demetra/services/agents/opencode.py:17,51,82,107,136,163` and resolve `OPENCODE_PLAN_MODEL` etc. with the same fallback chain (`user_environment.get(...) or settings.OPENCODE[...]`) before the existing `OPENCODE["*_model"]` lookup. `OPENCODE_PATH` stays system-wide.
4. **`UV_PATH` → per-project env.** Add `env["UV_PATH"] = str(UV["path"])` next to the existing `VIRTUAL_ENV` / `UV_PROJECT_ENVIRONMENT` writes in `demetra/services/runtime/project.py:184-191`. Surface the key in the per-project env editor (already wired per MNT-161); the per-project `.venv` and `UV_PROJECT_ENVIRONMENT` already land here via `setup_project_venv`.
5. **Tests** in a new `tests/test_settings_layers.py` covering: (a) the user-shared env value wins over the `settings.py` default for `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` / `OPENCODE_PLAN_MODEL`; (b) the project env value wins over user-shared; (c) `LINEAR_STATE_TODO_ID` / `LINEAR_TEAM_ID` resolution reads from `user_environment`; (d) `UV_PATH` is present in `project.environment` after `setup_project_venv`. Reuse the fixtures from `tests/test_subprocess.py` for the merge-order assertions.

## Follow-ups

- `users.keys` (the encrypted `keys` column at `demetra/library/tables.py:59`, written by `demetra/services/persistence/database.py:1154` and the `PATCH /api/v1/users/me/keys` endpoint at `demetra/api/users.py:21`) is a vestigial per-user API-key field. With `OPENROUTER_API_KEY` now readable from user-shared env (MNT-170, PR #80), `users.keys` is redundant and can be dropped in a follow-up cleanup ticket along with the `update_user_keys` / `UserKeysUpdateRequest` plumbing.
- Audit logging for env changes (deferred per the MNT-161 follow-ups list).
- Complete step 5 test coverage: OpenCode model override, `UV_PATH` after `setup_project_venv`, project-over-user merge order.

## References

- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Related: [[2026-06-08-project-environment]]
- Related: [[2026-08-18-migrate-llm-groq-to-openrouter]]
- Related: [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]
- Implementation: [MNT-170 — Migrate workflow env vars to project/user env layers](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers)
- External: [MNT-169 — Remove/update settings (Linear)](https://linear.app/mnt/issue/MNT-169/removeupdate-settings)
