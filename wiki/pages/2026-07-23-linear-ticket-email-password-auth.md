---
title: Linear Ticket for Email/Password Authentication
date: 2026-07-23
type: investigation
status: resolved
session_id: ses_unknown
services: [auth, linear]
branch: mnt-148-plain-auth
tickets: [MNT-148]
tags: [auth, linear, planning, email-password, github-oauth, bcrypt]
related:
- 2026-08-03-auth-hardening-and-deps-bump.md
- 2026-07-24-plain-auth-review-followups.md
---

# Linear Ticket for Email/Password Authentication

## TL;DR

Investigated the GitHub-only auth flow end-to-end and created Linear ticket **MNT-148** for adding email/password auth alongside it. The ticket locks in 3 scope decisions (bcrypt, signup+login only, single `users` table) with file:line refs so the implementer can start without re-exploring the codebase.

## Net effect

Same `users` table, same JWT + `auth_token` cookie, same `/api/v1/github/me` shape — users can sign up with email/password or GitHub and get an identical session. No parallel identity model; implementation deferred.

## Auth subsystem as it stands

**Backend** `demetra/services/auth.py` — `AuthError` at `:8` (from `library/exceptions.py`), `authenticate_user` at `:136`, `create_jwt_token` `:90-100` / `verify_jwt_token` `:103-120`, `get_current_user` `:161-176` (inlined by every protected route).

**API** `demetra/api/github.py:111` — `GET /github/login`, `GET /github/callback` (14-day `auth_token` cookie), `GET /github/me`, `POST /github/logout`.

**DB** `demetra/library/tables.py:47-58` — `users`: `github_id UNIQUE NOT NULL`, `email` nullable non-unique, `keys` (Fernet JSON); `jwt_tokens`: full JWT as PK. No `password_hash`, no bcrypt lib.

**Token/cookie** — HS256, 14-day `JWTConfig` (`settings.py:155-159`), `auth_token` httponly/secure/lax, mirrored to `localStorage` (read by `LogConsole.tsx:49` for WS in dev).

**Frontend** — `AuthContext.tsx`, `services/api.ts:3-7` (`User` missing `avatar_url`/`role`), `GitHubCallback.tsx`, `GitHubLoginButton.tsx`, `App.tsx:33-41` `LoginView` + inline `user ? <App> : <LoginView>`. No LoginForm/SignupForm.

**Tests** — `test_auth.py:230`, `test_api.py` 401 regressions, `conftest.py:669` fixtures; no password tests.

## Decisions (all recommended defaults)

1. **Hashing** → `bcrypt` via `passlib[bcrypt]` (later changed to direct `bcrypt` — see [[2026-08-03-auth-hardening-and-deps-bump]])
2. **Scope** → signup + login only (no reset/verification)
3. **Account model** → single `users` table, `github_id` nullable, shared email, same JWT/cookie
4. **Team** → `M2` (picked after listing Vention + M2)

Explicitly excludes reset, verification, linking, rate limiting.

> **Status update (2026-08-27):** Password reset was excluded above but an admin `--resetpass` CLI shipped under MNT-148 anyway (see [[2026-07-24-plain-auth-review-followups]] Step 4) — operator CLI, not self-service forgot-password.

## Linear API calls

`Linear_list_teams` → Vention + M2; `Linear_list_projects(query="Demetra", team="M2")` → Demetra project (`59773b61-…`); `Linear_save_issue` → **MNT-148** (priority 2, Backlog, branch `feature/mnt-148-…`).

## Ticket anatomy

Summary + Current State + Goal + Decisions + Tech Requirements (DB migration, BE `/api/v1/auth` router, FE forms, tests) + Out of Scope + 16 Acceptance Criteria + Key Files + file:line References.

## Open questions

- **Email uniqueness** — may collide with existing GitHub users; migration must backfill or fail loudly.
- **Account linking** — schema (`password_hash`/`github_id` nullable + CHECK) supports future linking; not in ticket.
- **`AuthError(LinearError)`** at `auth.py:20` → should be `DemetraError`; **fixed 2026-07-24** as `class AuthError(DemetraError)` in `exceptions.py:41` (commit `63e02ea`).

## Test Results

No code changes — ticket is the deliverable.

## Follow-ups

- Move MNT-148 to `In Progress` and branch `feature/mnt-148-…` when starting.
- Open separate tickets for reset, verification, linking, rate limiting.
- ~~Fix `AuthError` parent~~ **Done 2026-07-24**.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- External: [MNT-148](https://linear.app/mnt/issue/MNT-148/featauth-add-emailpassword-authentication-alongside-github-oauth) · [Demetra project](https://linear.app/mnt/project/demetra-a41f780f8bdc)
