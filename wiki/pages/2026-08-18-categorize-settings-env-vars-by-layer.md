---
title: Categorize settings env vars by layer
date: 2026-08-18
type: investigation
status: resolved
session_id: '-'
services:
- settings
- subprocess
- workflows
- persistence
branch: feature/mnt-169-removeupdate-settings
tickets:
- MNT-169
- MNT-170
tags:
- environment
- settings
- project-env
- user-env
- layers
- subprocess
related:
- 2026-08-10-process-environment-3-layers-encryption-uv-venv.md
- 2026-07-23-session-tokens-audit-revalidation.md
- 2026-08-18-migrate-llm-groq-to-openrouter.md
- 2026-08-19-split-auth-linear-services-and-review-failure-handling.md
---
# Categorize settings env vars by layer

## TL;DR

Classified every workflow env var in `demetra/settings.py` into three layers — **project** (`project_environment`), **user** (`user_environment` `scope='user'`), or **system** (stays in `settings.py`, overridable by user-shared env via OS→user→project→step merge). Plumbing exists per [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]; runtime work tracked as MNT-170. Key decisions: one Linear workspace → OAuth/labels system, `LINEAR_TEAM_ID`/states → user; `OPENROUTER_BASE_URL` system, key/model → user; `UV_PATH` → project.

> **Status update (2026-08-23):** MNT-170 merged via PR #80. Steps 1–4 done — `get_linear_config_value()` (`linear/__init__.py`), OpenRouter fallback (`llm/config.py`), `_resolve_opencode_model(..., user_environment=...)` (`agents/opencode.py`), `env["UV_PATH"]` (`runtime/project.py:187`). (2026-08-28) OpenCode per-agent overrides covered in `tests/test_opencode.py:TestOpencodeEnvLayers`; `UV_PATH` test still pending.

---

## Section 1 — Project (per-project `project_environment`)

Via `build_subprocess_env` (`runtime/subprocess.py:31`).

| Env var | Settings | Read by |
| --- | --- | --- |
| `UV_PATH` | `settings.py:155` | `runtime/project.py:174` (`uv venv`), `runtime/utils.py:128` (`uv tree`); alongside `VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT` in `setup_project_venv:185` |

## Section 2 — User (per-user `user_environment`, `scope='user'`)

Via `get_user_environments_decrypted` (`persistence/database.py:1565`), merged before project layer (`workflows/setup.py:50`).

| Env var | Settings | Read by |
| --- | --- | --- |
| `LINEAR_TEAM_ID` | `settings.py:119` | `linear/__init__.py:283,97` |
| `LINEAR_STATE_PRD_ID` | `settings.py:124` | `linear/__init__.py:131` |
| `LINEAR_STATE_TODO_ID` | `settings.py:125` | `linear/__init__.py:83,240` |
| `LINEAR_STATE_IN_PROGRESS_ID` | `settings.py:126` | Reserved (todo↔in_review loop) |
| `LINEAR_STATE_IN_REVIEW_ID` | `settings.py:127` | `linear/__init__.py:236` |
| `LINEAR_STATE_AWAITING_INPUT_ID` | `settings.py:128` | `daemons/watcher.py:49,98` |
| `LINEAR_STATE_DONE_ID` | `settings.py:129` | Reserved |
| `LINEAR_DEFAULT_STATE_ID` | `settings.py:131` | `linear/__init__.py:284` |
| `OPENROUTER_API_KEY` | `settings.py:191` | `llm/factory.py:25`; via `llm/openrouter.py` consumers |
| `OPENROUTER_MODEL` | `settings.py:192` | `llm/factory.py:21` |
| `GROQ_API_KEY` | `settings.py:186` | `llm/groq.py:37…` (legacy, parity treatment) |
| `GROQ_MODEL` | `settings.py:187` | Same legacy |

## Section 3 — System (stay in `settings.py`, overridable by user-shared env)

Ship as defaults; user-shared env may override at `build_subprocess_env:57`.

| Env var | Settings | Read by |
| --- | --- | --- |
| `OPENCODE_PATH` | `settings.py:136` | `agents/opencode.py:218…` |
| `OPENCODE_PLAN_MODEL` | `settings.py:137` | `agents/opencode.py:46` |
| `OPENCODE_RESOLVE_MODEL` | `settings.py:138` | `agents/opencode.py:182` |
| `OPENCODE_BUILD_MODEL` | `settings.py:139` | `agents/opencode.py:77,157` |
| `OPENCODE_VALIDATE_MODEL` | `settings.py:140` | `agents/opencode.py:131` |
| `OPENCODE_REVIEW_MODELS` | `settings.py:141` | `workflows/review.py` (one run per model) |
| `OPENROUTER_BASE_URL` | `settings.py:193` | `llm/factory.py:26` |
| `LINEAR_CLIENT_ID` | `settings.py:116` | `linear/oauth.py:24,41` |
| `LINEAR_CLIENT_SECRET` | `settings.py:117` | `linear/oauth.py:24,41` |
| `LINEAR_OAUTH_SCOPE` | `settings.py:118` | `linear/oauth.py:46` |
| `LINEAR_FEATURE_LABEL_ID` | `settings.py:122` | `linear/__init__.py:286` |
| `LINEAR_FILTER_LABELS` | `settings.py:132` | `linear/__init__.py:87,101` |
| `GIT_PATH` | `settings.py:159` | `vcs/git.py`, `runtime/project.py:140` |
| `GIT_WORKTREE_PATH` | `settings.py:160` | `vcs/git.py:43` |
| `GH_PATH` | `settings.py:164` | `vcs/github.py` |
| `CURSOR_PATH` | `settings.py:147` | `agents/cursor.py:36` |
| `CODERABBIT_PATH` | `settings.py:151` | `agents/coderabbit.py:30` |

## Out of scope (not passed to subprocesses)

App/DB/auth/logging only, stay in `settings.py`:
- DB/Redis: `DB_HOST/PORT/USER/NAME/PASSWORD`, `REDIS_URL`
- Crypto: `SECRET_KEY`, `ENCRYPTION_SALT`, `JWT_SECRET_KEY`, `DEFAULT_USER_ID`
- Logging/paths: `LOG_PATH/LEVEL`, `PARENT_HOME`, `PROJECTS_PATH`
- Limits: `MAX_BUILD/REVIEW/MERGE/REBASE/PLAN/RUN/LISTENER_ATTEMPTS`, `SUBPROCESS_TIMEOUT`, `CONTEXT_COMPACTION_THRESHOLD`
- Flags/wiki: `IS_RUFF/PYTEST_ENABLED`, `WIKI_LLM_BUDGET_*`, `WIKI_REVALIDATION_ENABLED`, `WIKI_DIFF_HUNK_CAP/BUILD_PLAN_CAP`
- Daemons: `WATCHER/LISTENER_POLL_INTERVAL`, `IS_ALLOWLIST_ENABLED`, `ALLOWLIST_SEED_FILE`, `OS_ENV_PROJECT_OPTINS/ALLOWLIST`, `COOKIE_*`, `CORS_ALLOWED_ORIGINS`, `DEBUG`

---

## Follow-up migration plan (MNT-170)

1. **Linear states+team → user-shared env.** `LINEAR[...]` lookups (`linear/__init__.py:83,236,240,283`, `watcher.py:49,98`) → `get_linear_state(name, *, user_id)` reading `user_environment[name]` then `settings.LINEAR[...]`. Thread via `Context` or resolver param; seed existing users from defaults.
2. **OpenRouter key/model → user overrides.** `llm/factory.py:21,25` fallback `user_environment.get(...) or settings.OPENROUTER[...]`; `base_url` stays system; thread `user_environment` into `build_llm()` from 4 call sites (`workflows/plan,review,cleanup`, `services/wiki`).
3. **OpenCode models → user overrides.** Thread `user_environment` into `opencode_*_agent` helpers (`agents/opencode.py:17…`), resolve `OPENCODE_*_MODEL` same fallback; `OPENCODE_PATH` stays system.
4. **`UV_PATH` → per-project env.** `env["UV_PATH"] = str(UV["path"])` beside `VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT` (`runtime/project.py:184`).
5. **Tests** `tests/test_settings_layers.py`: user wins over default for `OPENROUTER_API_KEY/MODEL`/`OPENCODE_PLAN_MODEL`; project>user; `LINEAR_STATE_TODO_ID`/`TEAM_ID` resolution; `UV_PATH` in `project.environment`.

> **Consistency note (2026-09-02):** new system settings: `AUTH_RATE_LIMIT_MAX` (10), `AUTH_RATE_LIMIT_WINDOW` (3600), `OAUTH_STATE_COOKIE`, `AUTH_COOKIE_NAME`; validation constants moved to `library/env.py`; limits retuned `MAX_BUILD=50`, `REVIEW/MERGE/REBASE=10`.

## Follow-ups

- Drop vestigial `users.keys` / `update_user_keys` (redundant with user-shared `OPENROUTER_API_KEY`).
- Audit logging for env changes; remaining test coverage for `UV_PATH` and project-over-user order.

## References

- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]], [[2026-07-23-session-tokens-audit-revalidation]], [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]
- External: [MNT-170](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers), [MNT-169](https://linear.app/mnt/issue/MNT-169/removeupdate-settings)
