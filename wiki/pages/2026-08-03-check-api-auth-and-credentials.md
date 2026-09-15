---
title: Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene
date: 2026-08-03
type: implementation
status: resolved
session_id: mnt-156-check-api-auth
services: [auth, api, watcher, react]
branch: mnt-156-check-api-auth
tickets: [MNT-156, MNT-81]
tags: [auth, cookies, csrf, origin-validation, websockets, ownership, api, refactor, routers]
related: [2026-07-23-linear-ticket-email-password-auth.md, 2026-07-24-plain-auth-review-followups.md, 2026-08-06-allowlist-review-fixes.md, 2026-08-09-apply-code-review-findings.md, 2026-06-01-refactor-api.md]
---

# Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene

## TL;DR

Tightened API auth on three axes: (1) replaced ~10 hand-rolled cookie/`get_current_user` checks with `Depends(get_current_user_dep)`; (2) scoped session lookups by `user_id` so users can't read/stream/delete others' sessions; (3) fixed WebSocket close codes (4001/4003/4000/4004) to reach clients via accept-then-close, and added React Origin guard for credentialed mutations.

## Step 1 — Shared auth dependency (commit `a1e479d`)

**`demetra/services/auth.py:241`** — new dependency replacing repeated:

```python
async def get_current_user_dep(auth_token: str | None = Cookie(default=None)) -> UserResponse:
    if not auth_token: raise HTTPException(401, "Not authenticated")
    if not (user := await get_current_user(token=auth_token)): raise HTTPException(401, "Invalid token")
    return user
```

`demetra/api/github.py|projects.py|sessions.py|users.py` now use `user: UserResponse = Depends(get_current_user_dep)`; `GET /github/me` → `return user`. Consistent 401 contract across routers.

## Step 2 — Session ownership scoping

**`demetra/services/database.py:482`** — `get_session_step_name(task_id, user_id=None)` adds `where(sessions.c.user_id == user_id)` when set. Watcher verifies `get_session_id_by_task_id(task_id, user_id)` before streaming (new `4004 Session not found`), passes `user_id` into all step lookups.

## Step 3 — WebSocket close-code delivery (working tree)

`websocket.close()` before `accept()` only fails the HTTP handshake — code lost. Now:

```python
async def reject_connection(ws, *, code, reason):
    try: await ws.accept(); await ws.close(code=code, reason=reason)
    except RuntimeError: pass
```

Paths: `4001` no token, `4003` forbidden, `4000` invalid task_id/log path, `4004` session not found.

## Step 4 — React credential hygiene + Origin guard

**`react/src/services/api.ts`** — previously `credentials:'include'` on every request. Now:

- `authenticatedFetch` adds `credentials:'include'` and, for mutating methods (POST/PATCH/PUT/DELETE), runs `assertTrustedOrigin(input)` (checks `target.origin == API_ORIGIN` from `VITE_API_URL`) before dispatch.
- `authFetch` originally dropped credentials (later restored — see correction). **Correction (2026-08-19):** removing credentials broke `Set-Cookie` on cross-origin login/signup; [[2026-08-09-apply-code-review-findings]] restored `credentials:'include'` on both.

All credentialed reads/mutations go through `authenticatedFetch`. `AuthContext.tsx` logout now reuses `api.logout()` (drops inline `API_URL`).

## Step 5 — Tests

- **`tests/test_api_auth.py`** (176 lines): `TestGetCurrentUserDep` (401 cases), `TestCrossUserIsolation` (`cross_user_client` fixture), `TestWatcherWebSocketOwnership`.
- **`tests/conftest.py`:** patches `demetra.services.auth.get_current_user` (single source) + `cross_user_client` fixture.
- **`tests/test_api.py|test_database.py`:** retargeted patches, `test_get_session_step_name_scopes_by_user_id`.
- **Working tree:** rejection tests assert delivered close code (`receive()["code"] == 4001`) not `WebSocketDisconnect` exception.

## Step 6 — Config

`pyproject.toml` `1.15.4`→`1.16.0` (later superseded by `1.15.5` in `5bcce84`); ruff `flake8-bugbear.extend-immutable-calls = ["fastapi.Depends"]`; locks regenerated.

## Test Results

60 API/auth tests, 7 watcher WS tests — all passed. `ruff`/`ty` clean. React `tsc+vite build` + 34 vitest passed.

## Source — [[2026-06-01-refactor-api]]

Thin `demetra/api/` routers by prefix (auth/github, projects, sessions, users, watcher, webhooks) — MNT-81, 2026-06-01. This page's `Depends` consolidation threads that layout; `api/tickets.py` removed by MNT-88.

## Follow-ups

- ~~Commit + PR `mnt-156-check-api-auth`~~ **Done** PR #66 (`8abcd8d`); follow-up PR #67 (`bcddc00`). Version trail superseded (master at `1.16.6`).
- Two anchors now stale (commit `04436c6`, 2026-08-07): `auth.py:241` → `auth/sessions.py:201` (re-exported), `database.py:482` → `persistence/database.py:701`. Further auth reorg: `2026-08-19-split-auth-linear-services-and-review-failure-handling.md`.

## References

- Linear: MNT-156
- Related: [[2026-07-24-plain-auth-review-followups]], [[2026-07-23-linear-ticket-email-password-auth]], [[2026-08-06-allowlist-review-fixes]]
