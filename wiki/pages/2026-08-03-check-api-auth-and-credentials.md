---
title: Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene
date: 2026-08-03
type: implementation
status: resolved
session_id: mnt-156-check-api-auth
services: [auth, api, watcher, react]
branch: mnt-156-check-api-auth
tickets: [MNT-156]
tags: [auth, cookies, csrf, origin-validation, websockets, ownership]
related: [2026-07-23-linear-ticket-email-password-auth.md, 2026-07-24-plain-auth-review-followups.md, 2026-08-06-allowlist-review-fixes.md, 2026-08-09-apply-code-review-findings.md]
---

# Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene

## TL;DR

The `mnt-156-check-api-auth` branch (1 commit ahead of master, plus current
working-tree changes) tightened API auth on three axes: (1) replaced ~10 copies of
hand-rolled cookie parsing / `get_current_user` checks in the routers with a single
`Depends(get_current_user_dep)` dependency; (2) scoped session step and ownership
lookups by `user_id` so users can't read/stream/delete another user's sessions; and
(3) made WebSocket rejection close codes (4001/4003/4000/4004) actually reach clients
by accepting-then-closing, and stopped the React client from sending
`credentials: 'include'` on non-authenticated calls while adding an Origin guard for
credentialed mutating requests.

---

## Overview

This page documents everything on the branch **`mnt-156-check-api-auth`** against
`master` — both the latest commit `a1e479d` (`MNT-156: Check API auth`) and the
current uncommitted working-tree changes on top of it.

```
master ── 3d6f353
   └── mnt-156-check-api-auth ── a1e479d (latest commit)
                                     └── working tree (this session's fixes)
```

- Commit `a1e479d`: backend auth dependency consolidation, session ownership
  scoping, React API client baseline, tests, config.
- Working tree (uncommitted): WebSocket close-code delivery fix, React Origin guard
  for credentialed mutations, AuthContext logout dedup, updated tests.

## Step 1 — Shared auth dependency (commit)

**File:** `demetra/services/auth.py:241`

Every protected endpoint previously repeated the same boilerplate:

```python
if not auth_token:
    raise HTTPException(status_code=401, detail="Not authenticated")
if not (user := await get_current_user(token=auth_token)):
    raise HTTPException(status_code=401, detail="Invalid token")
```

Added a single FastAPI dependency that encapsulates it:

```python
async def get_current_user_dep(auth_token: str | None = Cookie(default=None)) -> UserResponse:
    """FastAPI dependency that resolves the authenticated user from the auth cookie."""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

**Files:** `demetra/api/github.py`, `demetra/api/projects.py`,
`demetra/api/sessions.py`, `demetra/api/users.py` — all protected endpoints now
declare `user: UserResponse = Depends(get_current_user_dep)` instead of taking
`auth_token: str | None = Cookie(...)` and validating manually. `GET /github/me`
was reduced to just `return user`. This removed ~10 duplicated auth checks and made
the 401 contract consistent (`Not authenticated` when missing, `Invalid token` when
invalid) across projects, sessions, users, and the GitHub `/me` endpoint.

## Step 2 — Session ownership scoping (commit)

**Files:** `demetra/services/database.py:482`, `demetra/api/watcher.py`

`get_session_step_name` gained an optional `user_id` filter:

```python
async def get_session_step_name(task_id: str, user_id: str | None = None) -> tuple[str, str] | None:
    query = select(sessions.c.step, sessions.c.name).where(sessions.c.task_id == task_id)
    if user_id is not None:
        query = query.where(sessions.c.user_id == user_id)
    ...
```

The watcher now verifies session ownership with `get_session_id_by_task_id(task_id, user_id)`
before streaming logs (new `4004 Session not found` rejection), and passes `user_id`
into every step lookup so a user can't observe another user's session status.

## Step 3 — WebSocket close-code delivery (working tree)

**File:** `demetra/api/watcher.py:32`

`websocket.close(code=...)` called *before* `websocket.accept()` only fails the HTTP
handshake — uvicorn responds with a plain HTTP 403 and the application close code is
lost. All pre-accept rejection paths now accept first, then close, so the code reaches
the client:

```python
async def reject_connection(websocket: WebSocket, *, code: int, reason: str) -> None:
    """Accept the connection before closing so the application close code reaches the client."""
    try:
        await websocket.accept()
        await websocket.close(code=code, reason=reason)
    except RuntimeError:
        pass
```

Rejection paths converted: `4001` no auth token, `4003` forbidden, `4000` invalid
task_id / invalid log path, `4004` session not found.

## Step 4 — React credential hygiene and Origin guard (commit baseline + working tree)

**File:** `react/src/services/api.ts`

The client previously set `credentials: 'include'` on every request — including
signup/login/logout — which opts into cross-origin credentialed requests
unnecessarily. Now:

- `authFetch` — at the time of this session, plain fetch without `credentials: 'include'`
  (used by the non-authenticated calls: `exchangeCodeForToken`, `signup`, `loginWithPassword`,
  `logout`). **Correction (2026-08-19):** this removal was later identified as a regression —
  the browser ignored `Set-Cookie` on cross-origin login/signup responses. The fix in
  [[2026-08-09-apply-code-review-findings]] restored `credentials: 'include'` to `authFetch`;
  the current code has it on both `authFetch` and `authenticatedFetch`.
- `authenticatedFetch` — adds `credentials: 'include'` and, for mutating methods
  (POST/PATCH/PUT/DELETE), runs an Origin guard before dispatching:

```ts
function assertTrustedOrigin(input: RequestInfo | URL): void {
  if (typeof window === 'undefined' || !API_ORIGIN) return;
  const target = new URL(input.toString(), window.location.origin);
  if (target.origin !== API_ORIGIN) {
    throw new Error(`Blocked credentialed request to untrusted origin: ${target.origin}`);
  }
}

async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    assertTrustedOrigin(input);
  }
  return fetch(input, { ...init, credentials: 'include' });
}
```

`API_ORIGIN` resolves from `VITE_API_URL` (falls back to the page origin when the API
is same-origin). All credentialed reads (`getCurrentUser`, `getSessions`,
`getSessionHistory`, `getProjects`, `getProjectEnvironment`) and mutations
(`deleteSession`, `createProject`, `updateProject`, `deleteProject`,
`upsertProjectEnvironment`, `deleteProjectEnvironment`) now go through
`authenticatedFetch`.

**File:** `react/src/contexts/AuthContext.tsx` — `AuthProvider` had a duplicate
logout that called `fetch(..., { credentials: 'include' })` directly. It now reuses
the api client's `logout()` (no credentials) and drops the inline `API_URL` constant.

## Step 5 — Tests

**Commit — `tests/test_api_auth.py` (new, 176 lines):**

- `TestGetCurrentUserDep` — unit tests for `get_current_user_dep`: 401 without token,
  401 with invalid token.
- `TestCrossUserIsolation` — cross-user tests using a new `cross_user_client`
  fixture (another user's `UserResponse`): cannot get/delete another's project, cannot
  list/upsert/delete another's environment.
- `TestWatcherWebSocketOwnership` — websocket rejects a task not owned by the user.

**Commit — `tests/conftest.py`:** `patch_get_current_user` now patches
`demetra.services.auth.get_current_user` (single source) instead of each router's
import, and adds the `cross_user_client` fixture.

**Commit — `tests/test_api.py`, `tests/test_database.py`:** patched tests retargeted
to `demetra.services.auth.get_current_user`; watcher tests mock
`get_session_id_by_task_id` and use `UserResponse`; new
`test_get_session_step_name_scopes_by_user_id`.

**Working tree — `tests/test_api.py`, `tests/test_api_auth.py`:** rejection tests
updated from `pytest.raises((WebSocketDisconnect, Exception))` to asserting the
delivered close code, since the connection is now accepted before being closed:

```python
with TestClient(app).websocket_connect(self.WS_PATH) as ws:
    message = ws.receive()
    assert message["type"] == "websocket.close"
    assert message["code"] == 4001
```

## Step 6 — Config

**File:** `pyproject.toml` — version `1.15.4` → `1.16.0`; ruff
`flake8-bugbear.extend-immutable-calls = ["fastapi.Depends"]` so `Depends()` calls
can be used in decorators without being flagged as mutable defaults.
`.opencode/package-lock.json` and `uv.lock` regenerated.

## Test Results

- Python: `tests/test_api.py`, `tests/test_api_auth.py`, `tests/test_api_coverage.py`
  — **60 passed**.
- Watcher suite (`TestWatcherLogsWebSocket` + `TestWatcherWebSocketOwnership`) — **7 passed**.
- `ruff check` and `ty check` — clean on changed files.
- React: `npm run build` (tsc + vite) succeeds; `npm test` — **34 passed**.

---

## Follow-ups

- ~~None — changes are uncommitted in the working tree on top of `a1e479d`; commit and
  open a PR for `mnt-156-check-api-auth` against `master`.~~ **Done** — merged as PR #66
  (`8abcd8d`); the follow-up auth-filter/cors/mcp work landed as PR #67 (`bcddc00`).
  _Status note (2026-08-03, Consistency Agent):_ the Step 6 version bump to `1.16.0`
  (in `a1e479d`) was superseded by `1.15.5` in `5bcce84`; master HEAD is at `1.15.5`.
  _Update (2026-08-24, Consistency Agent):_ master has since advanced to `1.16.5`
  (`pyproject.toml`); the version trail above is kept as the session record.

## References

- Linear: MNT-156
- Related: [[2026-07-24-plain-auth-review-followups]] (password auth, cookie-only sessions)
- Related: [[2026-07-23-linear-ticket-email-password-auth]] (auth investigation leading to MNT-148)
- Related: [[2026-08-06-allowlist-review-fixes]] (MNT-155 allowlist review fixes)
