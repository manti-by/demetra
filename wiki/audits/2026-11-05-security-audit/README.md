# Security Audit — CodeRabbit Findings (2026-11-05)

**Date:** 2026-11-05
**Source:** `manti-by-demetra-agent-findings.json` (CodeRabbit, generated `2026-11-05T10:16:48Z`, scan revision `a5376e97`)
**Revalidated against:** `HEAD` `42dae24` (`2026-11-03 16:57:59 +0300`)

The attached PDF `security-findings-manti-by-2026-11-04.pdf` could not be read by the
reviewing model; this audit is derived from the equivalent JSON export, which carries
the same 18 findings.

## Method

Every finding was re-checked against the current checkout (`read` + `grep`), so each
plan cites the **current** file/line locations rather than the scan snapshot (line
numbers have drifted since the scan revision). Result: all 18 findings remain
**Confirmed** as written, with minor line-number drift and the assumptions noted where
the scanner itself flagged them.

## Findings

| # | Severity | CWE | Finding | File |
|---|----------|-----|---------|------|
| 01 | low | CWE-863 | Watcher log WebSocket streams a foreign session's logs | `demetra/api/watcher.py` |
| 02 | medium | CWE-367 | Password-reset TOCTOU survives session issuance | `demetra/services/persistence/database.py` |
| 03 | medium | CWE-200 | LangSmith API key leaked into repo subprocess env | `demetra/library/models.py` |
| 04 | medium | CWE-59 | Root `chown` follows symlinks in app-writable home | `configs/docker-entrypoint.sh` |
| 05 | medium | CWE-78 | `GIT_SSH_COMMAND` project env injection | `demetra/services/runtime/subprocess.py` |
| 06 | low | CWE-862 | Listener dispatches merge/rebase without author permission | `demetra/services/daemons/listener.py` |
| 07 | low | CWE-287 | Password signup skips email-ownership verification | `demetra/services/auth/sessions.py` |
| 08 | low | CWE-117 | Log injection via waitlist email control characters | `demetra/services/auth/waitlist.py` |
| 09 | medium | CWE-426 | Entrypoint resolves `id`/`setpriv` through untrusted PATH | `configs/docker-entrypoint.sh` |
| 10 | medium | CWE-863 | Watcher selects project by display name, not resolved id | `demetra/services/daemons/watcher.py` |
| 11 | medium | CWE-59 | Branch-name worktree path deletion outside worktree | `demetra/services/vcs/git.py` |
| 12 | medium | CWE-200 | MCP `query_table` leaks `password_hash` and env values | `demetra/tools/database.py` |
| 13 | low | CWE-352 | Logout has no CSRF / origin validation | `demetra/api/auth.py` |
| 14 | medium | CWE-306 | RQ dashboard exposed without authentication | `configs/nginx.conf` + `docker-compose.yaml` |
| 15 | medium | CWE-863 | Linear-link ownership takeover via session upsert | `demetra/services/linear/tasks.py` |
| 16 | medium | CWE-200 | `file://` URL accepted for service-managed clone | `demetra/services/runtime/project.py` |
| 17 | low | CWE-1385 | Watcher WebSocket does not validate `Origin` | `demetra/api/watcher.py` |
| 18 | medium | — | Pytest runs repository code with worker identity | `demetra/services/runtime/subprocess.py` |

## Plans

- [01 — Watcher log ownership bypass](01-watcher-logs-ownership-bypass.md)
- [02 — Password-reset TOCTOU](02-password-reset-session-toctou.md)
- [03 — LangSmith key leak](03-langsmith-key-leak-to-subprocess.md)
- [04 — Entrypoint chown symlink](04-entrypoint-chown-symlink.md)
- [05 — GIT_SSH_COMMAND injection](05-git-ssh-command-injection.md)
- [06 — Listener missing author check](06-listener-missing-author-check.md)
- [07 — Signup email ownership](07-signup-email-ownership.md)
- [08 — Waitlist log injection](08-waitlist-log-injection.md)
- [09 — Entrypoint PATH hijack](09-entrypoint-path-hijack.md)
- [10 — Watcher project-name binding](10-watcher-project-name-binding.md)
- [11 — Worktree branch path traversal](11-worktree-branch-path-traversal.md)
- [12 — MCP database sensitive columns](12-mcp-database-sensitive-columns.md)
- [13 — Logout CSRF](13-logout-csrf.md)
- [14 — RQ dashboard auth](14-rq-dashboard-auth.md)
- [15 — Linear-link ownership takeover](15-linear-link-ownership-takeover.md)
- [16 — file:// git clone](16-file-url-git-clone.md)
- [17 — Watcher WebSocket origin](17-watcher-websocket-origin.md)
- [18 — Pytest worker identity isolation](18-pytest-worker-identity-isolation.md)
