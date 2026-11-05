# 17 — Watcher WebSocket does not validate `Origin`

## Summary

- **Title:** Cross-site page can read logs over an ambient-cookie WebSocket
- **Problem:** `watcher_logs` authenticates the ambient `auth_token` cookie but accepts
  the WebSocket without validating the initiating `Origin`. When cross-site cookie
  attachment is enabled, an attacker page can open the log WebSocket with a known task
  UUID and receive the victim's log JSON using the victim's authenticated identity.
- **Date:** 2026-11-05
- **Severity:** low · **CWE-1385** · **Category:** csrf
- **CodeRabbit ID:** `157cfe51-177c-4f09-b8d2-be64146862b8`
- **Files (current):** `demetra/api/watcher.py:71-127` (`watcher_logs`)
- **Revalidation:** Confirmed. No `Origin` check exists anywhere in `watcher.py`; the
  connection is accepted at `watcher.py:127` after cookie auth only.

## Steps

1. Read the `origin` header from the WebSocket handshake and validate it against
   explicitly trusted frontend origins (reuse `CORS_ALLOWED_ORIGINS` or a dedicated
   `WS_ALLOWED_ORIGINS` setting in `demetra/settings.py`).
2. Define a deliberate policy for a missing `origin` (reject by default for
   cookie-authenticated connections; optionally allow only non-cookie/debug flows).
3. Reject with `reject_connection(..., code=4003)` when the origin is untrusted before
   `await websocket.accept()`.
4. If cross-site access is genuinely required, bind the connection to a short-lived
   token obtained through a protected application flow instead of the ambient cookie.
5. Add tests: a foreign/missing `Origin` is rejected; a trusted `Origin` connects.
