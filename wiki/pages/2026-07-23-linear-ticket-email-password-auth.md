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
related: [2026-08-03-auth-hardening-and-deps-bump.md, 2026-07-24-plain-auth-review-followups.md]
---

# Linear Ticket for Email/Password Authentication

## TL;DR

Investigated the current GitHub-only auth flow (BE, FE, DB, tests) and produced a comprehensive Linear ticket **[MNT-148](https://linear.app/mnt/issue/MNT-148/featauth-add-emailpassword-authentication-alongside-github-oauth)** for adding email/password auth alongside it. The ticket locks in three scope decisions via clarifying questions, and covers DB migration, BE service+API, FE forms+context, and tests with file-level line references to the current code.

---

## Net effect

Demetra currently exposes only GitHub OAuth. The new ticket adds a **plain email/password** flow that lives **side-by-side** with the existing GitHub flow: same `users` table, same JWT, same `auth_token` cookie, same `/api/v1/github/me` shape. No parallel identity model. The user can sign up with email + password *or* sign in with GitHub and end up with an identical session. Implementation is intentionally deferred to a future session.

## Auth subsystem as it stands

Mapped the current auth surface end-to-end to anchor the ticket in real code:

**Backend service** — `demetra/services/auth.py`
- `AuthError` at `auth.py:8` is imported from `demetra/library/exceptions.py` (note for follow-up: should likely subclass `DemetraError`)
- `authenticate_user(GitHubUser)` at `auth.py:136` — only entry point
- `create_jwt_token` at `auth.py:90-100` and `verify_jwt_token` at `auth.py:103-120` — to be reused unchanged
- `logout` at `auth.py:157-158` — to be reused unchanged
- `get_current_user` at `auth.py:161-176` — the auth dependency every protected route inlines manually

**Backend API** — `demetra/api/github.py:111`
- `GET /api/v1/github/login` (initiates OAuth, sets `oauth_state` cookie)
- `GET /api/v1/github/callback` (exchanges code, sets `auth_token` cookie, 14-day max-age)
- `GET /api/v1/github/me` (returns current user)
- `POST /api/v1/github/logout` (invalidates JWT, deletes cookie)
- All other protected routes (`/projects`, `/sessions`, `/users/me/keys`, `/ws/v1/watcher/logs`) inline the same `auth_token` cookie + `get_current_user` check.

**Database** — `demetra/library/tables.py:47-58`
- `users`: `id` PK, `github_id String NOT NULL UNIQUE`, `github_username String NOT NULL`, `email String` (nullable, **not unique**), `avatar_url`, `role` default `'user'`, `keys` (Fernet-encrypted JSON), `created_at`
- `jwt_tokens`: `token` PK, `user_id`, `expires_at`, `created_at` — full JWT string is the PK, enables server-side revocation
- No `password_hash` column, no password-hashing library (`bcrypt`/`argon2`/`passlib`) anywhere in `pyproject.toml` or imports

**Token & cookie**
- HS256 JWT, 14-day expiry (`JWTConfig` at `settings.py:155-159`)
- `auth_token` cookie: httponly, secure, samesite=lax, 14-day max-age
- Also mirrored to `localStorage` under `auth_token` and `user` keys for the FE
- `localStorage` `auth_token` is read by `react/src/components/LogConsole.tsx:49` for the WebSocket URL query param (dev mode only)

**Frontend** — `react/src/`
- `AuthContext.tsx` (`user` hydrated from `localStorage`, `login()` does redirect, `logout()` clears local + POSTs to GitHub logout)
- `services/api.ts` — `User` interface at `api.ts:3-7` missing `avatar_url` and `role`
- `pages/GitHubCallback.tsx` — handles OAuth `code`/`state`, calls `exchangeCodeForToken`
- `components/GitHubLoginButton.tsx` — SVG + "Sign in with GitHub"
- `App.tsx:33-41` — `LoginView`; `App.tsx:111-137` — inline `user ? <App> : <LoginView>` check (no protected-route wrapper)
- No LoginForm / SignupForm / password reset / email verification components exist

**Tests** — `tests/`
- `test_auth.py:230` — GitHub flow unit + API tests
- `test_api.py` — many `*_returns_401_without_auth_token` regression tests across protected endpoints
- `conftest.py:669` — `auth_cookie`, `authenticated_client`, `create_test_user` fixtures
- No tests for password hashing, signup, login, or password reset

## Decisions locked in via clarifying questions

Asked the user four questions to nail down scope before writing the ticket; all four answers were the recommended defaults:

1. **Hashing library** → `bcrypt` via `passlib[bcrypt]` (mature, FastAPI-standard, one dep) — *historical note (2026-08-04, Consistency Agent):* the implementation later dropped `passlib` in favor of a direct `bcrypt` dependency — see [[2026-08-03-auth-hardening-and-deps-bump]].
2. **Scope** → signup + login only (no password reset, no email verification — separate tickets)
3. **Account model** → single `users` table, shared email, `github_id` becomes nullable, same JWT/cookie for both flows
4. **Team** → `M2` (chosen after listing both available teams: Vention and M2)

The ticket body explicitly excludes password reset, email verification, account linking, and rate limiting as separate follow-ups so this ticket stays small and mergeable.

> **Status update (2026-08-27, Consistency Agent):** Scope drift versus decision 2. Despite
> password reset being locked out of scope here (deferred to "a separate ticket"), an
> admin-only `--resetpass` CLI (`reset_password_cli`) shipped inside this same MNT-148 branch
> during the first-pass review follow-ups — see [[2026-07-24-plain-auth-review-followups]]
> Step 4 ("Password reset CLI"). No wiki page for a distinct password-reset Linear ticket
> exists, so the "Open separate Linear tickets for: password reset..." follow-up below does
> not appear to have been actioned as its own ticket; the feature landed under MNT-148 instead.
> Note this is an operator/admin CLI reset, not the self-service "forgot password" email flow
> the ticket's exclusion was aimed at (no such user-facing flow exists in the current API —
> verified via `demetra/api/auth.py`), so the drift is partial, not a full reversal of the
> decision.

## Linear API calls performed

Resolved the team and project to attach to before creating the ticket:

- `Linear_list_teams` → returned Vention (`9ff43362-50d0-4bcd-827a-d524944d019a`) and M2 (`91a0fa70-7ac1-4065-8549-55c94c7f1c62`); user picked M2.
- `Linear_list_projects(query="Demetra", team="M2")` → returned Demetra project (`59773b61-cdd2-4f93-95ec-d6a5a1b5b33c`, status "In Progress"); user picked it explicitly.
- `Linear_save_issue(...)` → created **MNT-148** with priority `2` (High), status `Backlog`, in the Demetra project. Title, description, tech requirements, and acceptance criteria all included in the single create call. Linear auto-assigned the branch name `feature/mnt-148-featauth-add-emailpassword-authentication-alongside-github`.

## Ticket anatomy (what the body contains)

The ticket is organized so the implementer can start work without re-exploring the codebase:

- **Summary** + **Current State** + **Goal** (with file:line refs)
- **Decisions (locked)** — hashing, scope, account model, token reuse, API surface
- **Tech Requirements** — DB (Alembic migration spec), BE (services + new `/api/v1/auth` router), FE (forms + context + API client), Tests (new files + updates to existing conftest)
- **Out of Scope** — password reset, email verification, account linking, rate limiting, duplicate-email backfill
- **Acceptance Criteria** — 16 checkboxes covering migration, API behavior, security (bcrypt only, no plaintext in DB/logs), FE flows, regression of GitHub login, lint/type/test gates, and Conventional Commits PR title
- **Key Files Touched** — exact file list for the implementer
- **References** — file:line anchors into the current code

## Open questions

- **Migration risk:** making `email` unique may collide with existing GitHub users who share an email. Ticket instructs the migration to either backfill duplicates or fail loudly with a clear error — implementer's call.
- **Account linking:** the schema (nullable `github_id`, nullable `password_hash`, CHECK constraint that at least one is set) supports a future "link GitHub to password account" flow. Not in this ticket.
- **`AuthError` parent class:** was `AuthError(LinearError)` at `auth.py:20` (a known oddity — accidental inheritance, not a `DemetraError`). **Resolved 2026-07-24 during the MNT-148 implementation:** `AuthError` is now defined in `demetra/library/exceptions.py:41` as `class AuthError(DemetraError): pass` (commit `63e02ea`). The `auth.py:8` import was the only mention left there. Flagged here for traceability — ticket delivery unblocks it.

## Test Results

No code or tests were modified in this session — pure investigation + planning. The Linear ticket is the deliverable.

---

## Follow-ups

- Start a feature branch `feature/mnt-148-featauth-add-emailpassword-authentication-alongside-github` and move MNT-148 to `In Progress` when implementation begins (per AGENTS.md Linear workflow).
- Open separate Linear tickets for: password reset, email verification, account linking, auth-endpoint rate limiting.
- ~~Fix `AuthError(LinearError)` → `AuthError(DemetraError)` while in this area (one-line cleanup).~~ **Done 2026-07-24** (see Open questions above).

## References

- External: [MNT-148: feat(auth): add email/password authentication alongside GitHub OAuth](https://linear.app/mnt/issue/MNT-148/featauth-add-emailpassword-authentication-alongside-github-oauth)
- External: [Demetra project on Linear](https://linear.app/mnt/project/demetra-a41f780f8bdc)
