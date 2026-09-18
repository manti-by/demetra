---
title: Apply code-review findings — auth, transactions, validate, wiki
date: 2026-08-09
type: implementation
status: resolved
session_id: "-"
services: [auth, api, database, wiki, runtime, validation, react]
branch: "-"
tickets: []
tags: [code-review, auth, cookies, exceptions, transactions, wiki, validate, env, react]
related:
- 2026-08-09-wiki-fixes-and-test-optimization.md
- 2026-08-03-check-api-auth-and-credentials.md
- 2026-08-06-allowlist-review-fixes.md
- 2026-08-07-split-wiki-service-into-subpackage.md
---

# Apply code-review findings — auth, transactions, validate, wiki

## TL;DR

Applied all 7 findings from post-refactor review (`CODE_REVIEW_FINDINGS.md`, `v1.15.4..HEAD`): restored cross-origin auth cookies, rejected negative `env_get_int`, gated validate-agent on `Plan step N:` marker, made `reset_password`/`delete_project` atomic via `get_transaction()`, fixed `dedup_pages` and porcelain `-z` parsing, and replaced string-matched errors with typed exceptions. Version 1.16.2→1.16.3; 737 passed in 4.84s.

---

## Overview

Review of the large `services/{agents,auth,…}` refactor produced 7 findings (1 HIGH, 2 MEDIUM, 4 LOW). Fixes 5–6 land in `demetra/services/wiki/maintenance.py` alongside the new `revalidation_changed_files()` from [[2026-08-09-wiki-fixes-and-test-optimization]].

## Step 1 — HIGH: restore auth cookie on cross-origin requests

**File:** `react/src/services/api.ts:39`

`authFetch` forwarded `init` verbatim, dropping `credentials: 'include'` — browser ignored `Set-Cookie` cross-origin (5173→8000), every auth call 401'd.

```ts
const method = (init.method ?? 'GET').toUpperCase();
if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') assertTrustedOrigin(input);
return fetch(input, { ...init, credentials: 'include' });
```

## Step 2 — MEDIUM: `env_get_int` rejects negatives

**File:** `demetra/services/runtime/utils.py:215`

`int(os.environ.get(name, default))` accepted negatives; `SUBPROCESS_TIMEOUT=-1` killed every subprocess.

```python
try: value = int(os.environ.get(name, default))
except ValueError: return default
return value if value >= 0 else default
```

## Step 3 — MEDIUM: validate agent marker filter

**File:** `demetra/workflows/validate.py:10,47`

Every non-blank line was treated as missing item; stray prose burned retry budget. Now only `^Plan step \d+:` lines count.

```python
MISSING_ITEM_RE = re.compile(r"^Plan step \d+:", re.IGNORECASE)
if not MISSING_ITEM_RE.match(stripped): continue
```

## Step 4 — LOW: atomic `reset_password` under AUTOCOMMIT

**File:** `demetra/services/persistence/database.py:138`, `demetra/services/auth/__init__.py:412`

`isolation_level="AUTOCOMMIT"` made `session.begin()` a no-op — DELETE/UPDATE committed immediately, leaving partial state. New `get_transaction()` issues explicit `BEGIN/COMMIT/ROLLBACK`:

```python
async with get_connection(db_name) as connection:
    await connection.execute(text("BEGIN"))
    try: yield connection
    except BaseException: await connection.execute(text("ROLLBACK")); raise
    else: await connection.execute(text("COMMIT"))
```

`reset_password` and `delete_project` now use `async with get_transaction()`.

## Step 5 — LOW: `dedup_pages` keeps distinct-ticket pages

**File:** `demetra/services/wiki/maintenance.py:44,182`

Similarity ≥0.85 alone merged distinct tickets. New `is_duplicate_pair()` requires shared `tickets` entry or identical normalized title.

```python
left_tickets = {str(i).casefold() for i in (left_meta.get("tickets") or [])}
if left_tickets & right_tickets: return True
return bool(left_title) and left_title == right_title
```

## Step 6 — LOW: `revalidation_changed_files` parses `--porcelain=v1 -z`

**File:** `demetra/services/wiki/maintenance.py:289`

`line[3:]` mishandled renames (`R  old -> new`) and quoted spaces. Switched to NUL-separated output scoped to `wiki/` + `AGENTS.md`, consuming the second record for renames/copies.

```python
command = [str(service.GIT["path"]), "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "wiki/", "AGENTS.md"]
if code[0] in ("R", "C") and index < len(records): index += 1
```

## Step 7 — LOW: typed exceptions

**File:** `demetra/library/exceptions.py:45,49`, `demetra/api/auth.py:76`, `demetra/api/github.py:81`

`str(e) == "Email not authorized…"` was fragile. Added `RegistrationNotAllowedError`/`GitHubAccountNotAuthorizedError(AuthError)`, raised in `services/auth/__init__.py:260,211`, API checks via `isinstance`.

> **Status update (2026-09-02):** both subclasses removed by PR #119 — endpoint now raises plain `AuthError` (400) / `WaitlistedError` (202) and is IP rate-limited.

## Test Results

- New tests: `test_utils.py` (env_get_int), `test_validate_workflow.py` (stray prose), `test_wiki.py` (dedup, porcelain rename/space), `test_auth_password_api.py` (typed 403).
- Affected: 102 passed in 0.68s; full suite **737 passed in 4.84s**. Bump 1.16.3.

---

## Follow-ups

Working tree uncommitted on `master`; orchestrator handles commit/PR.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- External: [CODE_REVIEW_FINDINGS.md](../../CODE_REVIEW_FINDINGS.md) (`v1.15.4..HEAD`)
- Related: [[2026-08-03-check-api-auth-and-credentials]], [[2026-08-06-allowlist-review-fixes]], [[2026-08-09-wiki-fixes-and-test-optimization]], [[2026-08-07-split-wiki-service-into-subpackage]]
