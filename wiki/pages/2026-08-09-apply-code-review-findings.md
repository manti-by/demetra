---
title: Apply code-review findings — auth, transactions, validate, wiki
date: 2026-08-09
type: implementation
status: resolved
session_id: -
services: [auth, api, database, wiki, runtime, validation, react]
branch: -
tickets: []
tags: [code-review, auth, cookies, exceptions, transactions, wiki, validate, env, react]
related: [2026-08-03-check-api-auth-and-credentials, 2026-08-06-allowlist-review-fixes, 2026-08-09-wiki-fixes-and-test-optimization, 2026-08-07-split-wiki-service-into-subpackage]
---

# Apply code-review findings — auth, transactions, validate, wiki

## TL;DR

Applied all 7 findings from the post-refactor code review (`CODE_REVIEW_FINDINGS.md`, scope `v1.15.4..HEAD`): restored cross-origin auth cookies in the React client, rejected negative ints in `env_get_int`, gated validate-agent missing-items on a `Plan step N:` marker, made `reset_password`/`delete_project` atomic under AUTOCOMMIT via a new `get_transaction()` manager, stopped `dedup_pages` from merging distinct-ticket pages, switched `revalidation_changed_files` to `--porcelain=v1 -z` parsing, and replaced error-message string matching with typed exception subclasses. Version bumped 1.16.2 → 1.16.3; full suite **737 passed in 4.84s**.

---

## Overview

A review of the large `demetra/services/{agents,auth,...}` refactor plus the allowlist, wiki, MCP 2.0, stdin-prompt, validate-agent, and PR-failure features produced 7 findings (1 HIGH, 2 MEDIUM, 4 LOW). This session implemented fixes for all 7 in the working tree on `master`, each with a regression test. Findings 5 and 6 land in `demetra/services/wiki/maintenance.py` — the seam `revalidation_changed_files()` was added the same day in [[2026-08-09-wiki-fixes-and-test-optimization]], and this session fixes its parsing.

## Step 1 — HIGH: restore auth cookie on cross-origin requests

**File:** react/src/services/api.ts:39

`authFetch()` previously forwarded `init` verbatim, dropping the `credentials: 'include'` the login/signup/logout/GitHub-callback calls relied on, so the browser ignored the API's `Set-Cookie` cross-origin (React on :5173, API on :8000) — UI showed logged-in but every authenticated call 401'd, and `logout()` never revoked the server session.

```ts
// before
return fetch(input, init);
// after
const method = (init.method ?? 'GET').toUpperCase();
if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
  assertTrustedOrigin(input);
}
return fetch(input, { ...init, credentials: 'include' });
```

Also re-applies the Origin guard for mutating calls, consistent with [[2026-08-03-check-api-auth-and-credentials]].

## Step 2 — MEDIUM: `env_get_int` rejects negative values

**File:** demetra/services/runtime/utils.py:215

`int(os.environ.get(name, default))` accepted negatives despite the docstring's claim. `SUBPROCESS_TIMEOUT=-1` would expire every `asyncio.timeout` immediately and kill every subprocess; `MAX_BUILD_ATTEMPTS=-1` makes `while rerun_attempts:` false on entry and raises `InfiniteLoopError`.

```python
try:
    value = int(os.environ.get(name, default))
except ValueError:
    return default
return value if value >= 0 else default
```

## Step 3 — MEDIUM: validate agent only reports marker-prefixed items

**File:** demetra/workflows/validate.py:10,47

`run_validate_agent` treated every non-blank stdout line that wasn't an exact `NO_ISSUE` token as a missing plan item. Any stray prose ("I reviewed the staged diff…") forced another full build+validate cycle, burning `rerun_attempts`/`review_attempts` toward `InfiniteLoopError`. The review path avoids this by routing noisy output through Groq (`summarize_review`); here the cheaper fix is a marker filter.

```python
MISSING_ITEM_RE = re.compile(r"^Plan step \d+:", re.IGNORECASE)
...
if not MISSING_ITEM_RE.match(stripped):
    continue
```

## Step 4 — LOW: atomic `reset_password` under AUTOCOMMIT isolation

**File:** demetra/services/persistence/database.py:138; demetra/services/auth/__init__.py:412

The engine runs at `isolation_level="AUTOCOMMIT"`, so `session.begin()` was a no-op and each DELETE/UPDATE committed immediately — a mid-failure left JWT rows revoked while the password hash stayed old (partial state). The same latent non-atomicity hit `delete_project`. New manager issues the transaction control itself:

```python
async with get_connection(db_name) as connection:
    await connection.execute(text("BEGIN"))
    try:
        yield connection
    except BaseException:
        await connection.execute(text("ROLLBACK"))
        raise
    else:
        await connection.execute(text("COMMIT"))
```

`reset_password` (auth/__init__.py:412) and `delete_project` (database.py:1541) now use `async with get_transaction() as connection:`.

## Step 5 — LOW: `dedup_pages` keeps distinct-ticket pages

**File:** demetra/services/wiki/maintenance.py:44,182

`dedup_pages` deleted any page with Jaccard similarity ≥ 0.85 to another — two different auth-related tickets with overlapping wording exceeded the threshold and the older page was unlinked. Added `is_duplicate_pair()`: genuine duplicates require a shared `tickets` frontmatter entry **or** an identical normalized title; vocabulary similarity alone no longer merges.

```python
left_tickets = {str(item).casefold() for item in (left_meta.get("tickets") or [])}
right_tickets = {str(item).casefold() for item in (right_meta.get("tickets") or [])}
if left_tickets & right_tickets:
    return True
left_title = str(left_meta.get("title") or "").casefold().strip()
right_title = str(right_meta.get("title") or "").casefold().strip()
return bool(left_title) and left_title == right_title
```

Guarded behind `WIKI_REVALIDATION_ENABLED` (default `False`), but the guard now actually preserves distinct pages.

## Step 6 — LOW: `revalidation_changed_files` parses `--porcelain=v1 -z`

**File:** demetra/services/wiki/maintenance.py:289

`line[3:]` on `git status --porcelain` mishandled renames (`R  old -> new` became `"old -> new"`, so `git add` failed and the revalidation commit silently did nothing) and quoted paths with spaces. Switched to NUL-separated v1 output and skipped the rename/copy destination record:

```python
command = [str(service.GIT["path"]), "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "wiki/"]
...
records = stdout.split("\0")
...
code = record[:2]
path = record[3:]
if code[0] in ("R", "C") and index < len(records):
    index += 1
```

## Step 7 — LOW: typed exceptions replace message-string matching

**File:** demetra/library/exceptions.py:45,49; demetra/api/auth.py:76; demetra/api/github.py:81

The 403 signal was `str(e) == "Email not authorized for registration"` / `"GitHub account not authorized"` — reword the message and the frontend's 403 key breaks silently. Added `RegistrationNotAllowedError(AuthError)` and `GitHubAccountNotAuthorizedError(AuthError)`, raised in `services/auth/__init__.py:260,211`, and switched the API handlers to `isinstance` checks.

## Test Results

- New tests: `test_utils.py` (4 × `env_get_int`), `test_validate_workflow.py` (stray prose not reported), `test_wiki.py` (similar pages with distinct tickets kept; porcelain `-z` rename/space parsing; empty set on failure), `test_auth_password_api.py` (403 via typed exception).
- Affected files: **102 passed in 0.68s**.
- Full suite: **737 passed in 4.84s**.
- `pyproject.toml` + `uv.lock` bumped to 1.16.3.

---

## Follow-ups

- Working tree is uncommitted on `master`; the orchestrator handles the commit/PR (version bump suggests a release-style commit).

## References

- External: [CODE_REVIEW_FINDINGS.md](../../CODE_REVIEW_FINDINGS.md) — review target `v1.15.4..HEAD`, 7 findings
- Related: [[2026-08-03-check-api-auth-and-credentials]], [[2026-08-06-allowlist-review-fixes]], [[2026-08-09-wiki-fixes-and-test-optimization]], [[2026-08-07-split-wiki-service-into-subpackage]]
