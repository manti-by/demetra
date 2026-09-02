# Merged Code Review — `v1.16.7..HEAD` (Revalidated)

**Date:** 2026-09-02  
**Sources merged:** `CR_OPUS_v1.md` (11 findings), `CR_OPUS_v2.md` (7 findings), `CR_SONET_v1.md` (15 findings), `CR_SONET_v2.md` (15 findings) — 48 raw findings → 26 deduplicated groups  
**Validation method:** each finding re-checked against current `HEAD` source (`read` + `grep`), then checked against the current test/build baseline. Results: 19 active findings confirmed as written, 5 confirmed with qualifications, and 2 already fixed. File:line references are current.

---

## How to read

- **Confirmed** — bug/regression still present in checked-out HEAD.
- **Confirmed (qualified)** — the underlying issue is present, but its scope or consequence needed correction.
- **Fixed** — no longer present in HEAD (removed or patched since the review snapshot).
- **Partial** — part of the claim is fixed, remainder still applies.
- Overlapping reports are grouped; original IDs are kept for traceability.

---

## 1. Critical — Data loss / Crash

### 1.1 IndexError on whitespace-only review comment crashes after push — **Confirmed**

- **Sources:** OPUS_v2#1, SONET_v1#1, SONET_v2#4
- **Files:** `demetra/workflows/review_fixes.py:95-117`, `demetra/workflows/review_fixes.py:285-304`
- **Validation:** `_format_threads_for_comment` at lines 107-110 does `((comment.get("body") or "").strip().splitlines()[0][:120])` after filter `if comment.get("body")` (line 110). Whitespace `"  \n"` is truthy → passes filter → `.strip()` → `""` → `.splitlines()` → `[]` → `[0]` raises `IndexError`. Sibling `_format_threads_for_prompt` at line 81 correctly checks `if body:` *after* stripping, proving asymmetry. In `run_review_fixes_workflow` the call at line 287 is *after* `git_commit`/`git_force_push` (lines 274-283) but *before* `fix_succeeded=True` (line 298). `except (OSError, RuntimeError)` at line 302 does not catch `IndexError`, so the pushed fix lands but the PR summary comment and wiki recording are skipped. The `finally` block still removes the worktree. The RQ enqueue has no retry policy, so the job is marked failed rather than automatically retried.
- **Fix:** filter after strip, e.g. `body = (c.get("body") or "").strip(); if not body: continue` or `if body: bodies.append(body.splitlines()[0][:120])`.

### 1.2 Editing a masked `text`-type sensitive key overwrites it with literal `********` — **Confirmed**

- **Sources:** SONET_v2#1
- **Files:** `react/src/components/EnvSettingsModal.tsx:134-138`, `demetra/services/persistence/database.py:1834-1862` (`list_user_environments`), `demetra/api/projects.py:237-246`
- **Validation:** `beginEdit` blanks `draftValue` only when `entry.type === "encrypted"` (line 137). But backend masks `text` rows whose key matches `is_sensitive_key` (`TOKEN`/`SECRET`/`KEY`/`PASSWORD`) — `database.py:1861`, `projects.py:242`. User adds `API_KEY=sk-live-123` as `text`; list/upsert returns `value="********"`; Edit pre-fills `draftValue="********"`; Save calls `upsert(..., "********", "text")` and `upsert_*_environment` for non-encrypted stores `stored_value=value` verbatim → secret permanently replaced with mask string. Project-scope same via `projects.py:237`.
- **Fix:** `beginEdit` must blank or re-fetch when `isSensitiveKey(entry.key)` (or when `entry.value === ENCRYPTED_VALUE_MASK`), regardless of `type`.

### 1.3 Text→encrypted conversion (or blank encrypted create) silently stores encrypted empty string — **Confirmed**

- **Sources:** OPUS_v1#2, SONET_v1#2, SONET_v1#3, SONET_v2#2
- **Files:** `demetra/services/persistence/database.py:1618-1686` (`_fetch_stored_encrypted_value`, `_resolve_encrypted_env_value`), `react/src/components/EnvSettingsModal.tsx:299-300`
- **Validation:** `_resolve_encrypted_env_value:1679` `if value: encrypt` else lookup `keys=[key, previous_key]` for an *existing* `type=="encrypted"` row; returns `None` → `encrypt_str("")` (line 1685). So converting a `text` row to `encrypted` with blank value (or creating fresh encrypted with empty field) finds no encrypted row → encrypts `""`. Frontend placeholder `"leave blank to keep current value"` shown whenever `isEditing && draftEncrypted` (line 299) without checking original type, actively guiding the user into this. Same in old `EnvSettings.tsx`/`SharedEnvSettings.tsx`.
- **Fix:** Either disallow blank on type-change, require explicit value, or surface error; and make placeholder conditional on `originalType==="encrypted"`.

### 1.4 Whitespace-only value silently overwrites real encrypted secret — **Confirmed**

- **Sources:** SONET_v1#4
- **Files:** `react/src/components/EnvSettingsModal.tsx:179-227`, `demetra/services/persistence/database.py:1679`
- **Validation:** `beginEdit` leaves `draftValue=""` for encrypted entries so blank means "keep". But `handleSaveEdit` sends `draftValue` verbatim; `' '` is truthy in JS and Python `if value:` (line 1679) → treated as new plaintext → `encrypt_str(' ')` overwrites real secret with encrypted space. No trim/validation. Guard at line 192 only checks `!draftEncrypted && !draftValue` (disable-encryption case), not the encrypted-keep case.
- **Fix:** trim and treat whitespace-only as blank (`if not value.strip(): reuse`), or validate/reject whitespace.

---

## 2. High — State-machine / Silent no-op / Data integrity

### 2.1 Rename leaves duplicate rows / can clone unrelated ciphertext — **Confirmed**

- **Sources:** SONET_v1#6, SONET_v1#7, SONET_v2#3
- **Files:** `demetra/services/persistence/database.py:1618-1736`, `react/src/components/EnvSettingsModal.tsx:200-210`
- **Validation:**
  - *Clone:* `_fetch_stored_encrypted_value` accepts `keys=[key, previous_key]` and returns first encrypted match without verifying `previous_key` is the row being renamed; caller can pass any existing key as `previous_key` and new key inherits its ciphertext (scope-limited to same owner, but breaks 1:1 rename).
  - *Duplicate:* `handleSaveEdit` does `upsertEntry(newKey, ...)` then separate `deleteEntry(oldKey)` (lines 206-207). If delete fails (network drop, tab close, 5xx) the DB holds two live rows with same ciphertext; backend never deletes old row itself, no transaction. Same pattern in `SharedEnvSettings.tsx`. Original OPUS_v1#4 family noted same two-call rename.
- **Fix:** Backend should delete old key atomically when `previous_key != key` (or at least validate `previous_key` exists); frontend should reconcile on delete failure.

### 2.2 `get_unresolved_review_threads` swallows failures + misses general reviews + truncates via pagination — **Confirmed**

- **Sources:** OPUS_v1#1, OPUS_v1#5, SONET_v1#5, SONET_v1#15, SONET_v2#7
- **Files:** `demetra/services/vcs/github.py:110-189`, `demetra/workflows/review_fixes.py:220-238`
- **Validation:**
  - *Type coercion:* command at lines 149-161 uses `-f` for `query` but `-F` for `owner`/`name`/`pr`. `-F` JSON-coerces numeric strings; repo named `2024` sends `name` as int against `$name:String!` → GraphQL error → `exit_code!=0` → `return []`. Pr as `Int!` correctly uses `-F`, but owner/name should be `-f`. Still present in HEAD (review was correct).
  - *Swallow:* any non-zero exit or JSON parse returns `[]` indistinguishable from "zero threads" (lines 165-178). Caller at `review_fixes.py:228` posts "No unresolved review threads — nothing to fix" and returns `True`, silently ignoring transient CLI/rate-limit/auth failures.
  - *Pagination & general reviews:* query at line 144-145 only `reviewThreads(first:100)` + `comments(first:20)` with no `hasNextPage`/`endCursor`; truncates silently. And docstring claims "both inline and general" (line 122) but only `reviewThreads` (inline) are queried — `PullRequest.reviews{body}` never fetched, so Request-Changes summaries with no inline comments are lost.
- **Fix:** use `-f` for String vars; surface fetch failures distinctly (raise/return None) and skip the "nothing to fix" comment on error; add pagination or warning; optionally query `reviews` for general comments.

### 2.3 Review fix is not pushed if the build-agent commits instead of staging — **Confirmed (qualified)**

- **Sources:** OPUS_v1#4
- **Files:** `demetra/workflows/review_fixes.py:250-272`, `demetra/services/agents/opencode.py:175-209`
- **Validation:** workflow expects agent to *stage* only ("DO NOT commit or push, just stage" appended at lines 198/247). It then checks `has_staged = await git_add_all(...)` (line 261) and treats `False` as "no changes". If the agent commits, `git diff --staged` is empty → `has_staged=False` → workflow posts "found no changes" and returns `True` without pushing. Removing the worktree does not immediately delete the local branch or commit, but the next review-fixes run force-resets that branch from `origin/<head>`, making the unpushed commit effectively lost unless manually recovered. The defect is conditional on the agent violating its explicit no-commit instruction; no defensive check exists.
- **Fix:** detect commits (e.g. `git log --ahead` or `git status --porcelain` including committed diff vs `origin/<head>`), or explicitly `git reset --soft HEAD~1` / stage committed diff.

### 2.4 `approve_waitlist_entry` ordering / non-atomic / docstring contradiction — **Confirmed (qualified)**

- **Sources:** OPUS_v1#3, OPUS_v2#2, SONET_v2#10
- **Files:** `demetra/services/auth/waitlist.py:175-225`, `demetra/services/auth/waitlist.py:175-182` (docstring)
- **Validation:** Current order (lines 200-223): `notified_at = send_approval_email(entry)` → `add_entry(...)` → `update_waitlist_entry(status="approved"...)`. So:
  - Notification happens *before* the allowlist write: if `add_entry` raises non-`AuthError` (e.g. `SQLAlchemyError`) the user can be told they are approved but never allowlisted (OPUS_v1#3). The current notifier is log/console-only, not a real SMTP/provider integration, so the external-email consequence applies when the planned provider is added.
  - Docstring at line 180-182 says "flips to approved with notified_at only when notification succeeded (failure leaves pending so can be retried)" but code at line 217 always sets `status="approved"` and only `notified_at` is conditional (OPUS_v2#2) — pending-for-retry never happens. With real SMTP returning `False`, user becomes allowlisted+approved but never notified and cannot be retried.
  - No atomicity: `send → add → update` are three separate DB/email steps; transient failure between `add_entry` success and `update_waitlist_entry` leaves allowlisted+emailed but `status="pending"` (SONET_v2#10) → retry then hits duplicate `add_entry` → swallowed via `find_allowlist_entry` → duplicate email.
- **Fix:** order `add_entry` → `update(status=approved, notified_at=None)` → `send` → if send succeeds `update(notified_at=now)` else handle (or at least document & make `send` affect status as promised); consider transaction for DB steps.

### 2.5 Revoked-then-rejoined / re-blocked user has no path back to waitlist — **Confirmed (qualified)**

- **Sources:** OPUS_v2#3, SONET_v1#11, SONET_v2#11
- **Files:** `demetra/services/auth/waitlist.py:84-113`
- **Validation:** `join_waitlist` at line 110 only reopens when `existing["status"] == "rejected"` → `pending`. An email entry that is `approved` but whose user never registered remains stuck after allowlist removal: `signup_with_password` calls `join_waitlist`, which returns the old id without resetting its status. GitHub entries in either `approved` or `joined` state have the same problem because `authenticate_user` calls `join_waitlist` after the allowlist check fails. Existing password users are affected differently: `login_with_password` does not call `join_waitlist`, and a repeated signup is rejected as already registered, so the report's original claim that every password login/signup returns a fresh 202 was too broad.
- **Fix:** reopen `approved`/`joined` to `pending` (or at least `approved`) on re-join after allowlist removal, or add explicit `rejected`-like transition.

### 2.6 Successful research run leaves an orphaned git branch blocking reprocessing — **Confirmed**

- **Sources:** SONET_v2#5
- **Files:** `main.py:117-123`, `demetra/services/vcs/git.py:66-96`, `demetra/services/vcs/git.py:310-343`
- **Validation:** Research ticket path in `main.py:117-123` sets `is_success=True` and returns *without* pushing a branch/PR. `cleanup_workflow → git_cleanup` at line 334 returns early when `is_success` is true, so local branch is *never* deleted — orphaned with deterministic name. On reprocessing (ticket moved back to TODO, manual re-run) `setup_workflow → git_worktree_create` checks `worktree_path.exists()` (line 67) — worktree dir was removed earlier (so stale-branch cleanup missed) — then runs `git worktree add -b <branch>` (line 80) which fails because branch already exists → uncaught `RuntimeError` before `try/finally` in `main()`. Same head `git_branch_delete` never ran.
- **Fix:** delete branch for research success (or skip branch creation for research, or `git_branch_delete` there).

### 2.7 Unguarded `mark_waitlist_joined_by_value()` can 500 a successful login/signup — **Confirmed**

- **Sources:** SONET_v2#6
- **Files:** `demetra/services/auth/sessions.py:62`, `demetra/services/auth/sessions.py:125`, `demetra/api/github.py:81`, `demetra/api/auth.py:74`
- **Validation:** Both `authenticate_user` (line 62) and `signup_with_password` (line 125) call `await service.mark_waitlist_joined_by_value(...)` *after* `get_or_create_user`/`create_user` + `create_jwt_token` + `save_jwt_token`. No try/except. Callers only catch `WaitlistedError`/`AuthError`; `SQLAlchemyError` from the audit write propagates as unhandled 500 even though account+token were already created — client sees failed login for usable account.
- **Fix:** wrap audit call in try/except + log.

---

## 3. Medium — Robustness / UI correctness

### 3.1 `waitlisted_response` drops `entry_id` from JSON body — **Confirmed**

- **Sources:** OPUS_v2#6, SONET_v2#9
- **Files:** `demetra/api/responses.py:8-22`, `demetra/library/models.py:358-362`, `demetra/api/auth.py:77`, `demetra/api/github.py:82`
- **Validation:** `waitlisted_response` constructs `WaitlistedResponse(entry_id=entry_id)` but serializes only `{"status":..., "message":...}` (line 19) — `entry_id` dropped. `WaitlistedError.entry_id` is threaded all the way from `join_waitlist` → exception → `waitlisted_response(entry_id=e.entry_id)` but never reaches client. Both auth and github callback paths affected.
- **Fix:** include `entry_id` in body when present.

### 3.2 Dead 403 branches / unused exception classes — **Confirmed**

- **Sources:** OPUS_v2#4, SONET_v1#13, SONET_v2#14
- **Files:** `demetra/api/auth.py:79`, `demetra/api/github.py:84`, `demetra/library/exceptions.py:57-62`
- **Validation:** `signup_with_password` now raises `WaitlistedError` instead of `RegistrationNotAllowedError`; `authenticate_user` raises `WaitlistedError` instead of `GitHubAccountNotAuthorizedError`. Grep shows zero `raise RegistrationNotAllowedError`/`raise GitHubAccountNotAuthorizedError` in repo. So `403 if isinstance(e, ...)` always falls through to 400. Exceptions remain defined/imported but never raised — maintenance hazard.
- **Fix:** either remove or re-raise those types where appropriate, or collapse to 400.

### 3.3 Unauthenticated waitlist insertion is unbounded-growth / abuse vector — **Confirmed (by design)**

- **Sources:** OPUS_v1#6
- **Files:** `demetra/services/auth/sessions.py:46-50`, `demetra/services/auth/sessions.py:103-105`, `demetra/services/auth/waitlist.py:84-121`
- **Validation:** Any unauthenticated `POST /signup` or GitHub callback with valid-format email/login now writes a `waitlist_entries` row via `join_waitlist` (previously hard 403). No rate limit, CAPTCHA, or cap. Attacker can POST distinct valid emails → unbounded rows. Functionally intentional for waitlist, but abuse vector remains.
- **Fix:** add rate limiting / min interval / CAPTCHA / size cap.

### 3.4 Several agents do not receive project-scoped OS-env tokens — **Confirmed (qualified)**

- **Sources:** OPUS_v1#7
- **Files:** `demetra/services/agents/opencode.py:35-172`, `demetra/services/agents/opencode.py:244-309`, `demetra/workflows/research.py:55-61`
- **Validation:** `opencode_research_agent` lacks `project_id`; `run_opencode_agent` is called without it (lines 299-308), so `run_command` omits project-scoped OS-env opt-in passthrough (`OS_ENV_PROJECT_OPTINS`). This is broader than the original report stated: only the review-fixes and merge wrappers currently forward `project_id`; plan, build, review, validate, resolve, and research do not.
- **Fix:** add and forward `project_id` consistently for every project-scoped agent call.

### 3.5 `inert` attribute gets stuck after viewport resize past breakpoint — **Confirmed**

- **Sources:** SONET_v1#10, SONET_v2#12
- **Files:** `react/src/App.tsx:52`, `react/src/App.tsx:130`, `react/src/App.tsx:144`, `react/src/App.tsx:159`, `react/src/App.css:1609` (media query)
- **Validation:** `sidebarOpen` is pure React state; `Header` gets `inert={sidebarOpen}` and `.console-container` gets `{inert:""}` when true. CSS at 768px reflows drawer to desktop but JS state stays `true`; no `matchMedia`/resize listener. User opens drawer at narrow width then widens — header + console remain `inert` (unclickable/unfocusable) with no visual cue.
- **Fix:** listen to `(min-width: 769px)` and reset `sidebarOpen=false`.

### 3.6 Stale waitlist banner persists after login/signup mode toggle — **Confirmed**

- **Sources:** SONET_v1#12, SONET_v2#15
- **Files:** `react/src/components/PasswordAuthForm.tsx:79`, `react/src/components/PasswordAuthForm.tsx:86`
- **Validation:** Toggle buttons do `setMode(...); setError(null)` but never `setWaitlistMessage(null)`. `handleSubmit` clears both at start (line 15-16), but mode switch alone leaves prior `waitlistMessage` rendered above the other form.
- **Fix:** also `setWaitlistMessage(null)` on mode toggle.

### 3.7 `oauth_state` cookie deletion lost on waitlist exit path — **Confirmed**

- **Sources:** SONET_v1#14
- **Files:** `demetra/api/github.py:36-85`
- **Validation:** `github_callback` at line 52 calls `response.delete_cookie("oauth_state")` on injected `response`. But both the success path (lines 68-80) and the `WaitlistedError` path (line 82 `return waitlisted_response(...)`) construct a *brand-new* `Response` and return it, discarding the injected object's `Set-Cookie` deletion header. Stale cookie lingers until next login overwrites it.
- **Fix:** propagate deletion into the returned response (e.g. `waitlisted_response(...).delete_cookie("oauth_state")` or reuse injected `response`).

### 3.8 Facade re-exports unvalidated `list_waitlist_entries` — **Confirmed**

- **Sources:** SONET_v2#8
- **Files:** `demetra/services/auth/__init__.py:22`, `demetra/services/auth/waitlist.py:240-254`
- **Validation:** Public facade exports raw `list_waitlist_entries` (no status validation) instead of `list_entries()` wrapper which raises `ValueError` for invalid status. Caller can import from `demetra.services.auth` and query `status="approve"` (typo) silently getting empty list; CLI path `waitlist_cli → list_entries` is validated but facade consumers bypass it.
- **Fix:** export `list_entries` (or both, with wrapper).

### 3.9 Env key/mode duplication — **Confirmed (low severity)**

- **Sources:** OPUS_v1#9, OPUS_v2#5
- **Files:** `demetra/api/projects.py:34-36`, `demetra/api/users.py:17-19`, `demetra/api/projects.py:262-277`, `demetra/api/users.py:70-85`
- **Validation:** `ENV_KEY_RE`, `MAX_ENV_KEY_LENGTH`, `MAX_ENV_VALUE_LENGTH` and the validation blocks are duplicated verbatim between `projects.py` and `users.py`. Future limit/pattern change must be in two places or endpoints diverge. No shared module.
- **Fix:** extract to `demetra/library` or shared constant.

### 3.10 Session-dot indicator missing color for `research` step (and other new steps) — **Confirmed (qualified)**

- **Sources:** OPUS_v1#11
- **Files:** `react/src/App.css:978-1002`, `demetra/library/models.py:9-23` (StepType)
- **Validation:** `.session-dot` rules cover `step-initial`/`plan`/`build`/`review`/`completed`/`failed` only. `research`, `validate`, `awaiting_input`, `wiki`, `push`, `lint`, and `test` have no rule, so their dots are transparent. The original report also listed `merge`, but `merge` is not a current `StepType`.
- **Fix:** add `.session-dot.step-research` (and other `StepType`) colors.

### 3.11 Env modal doesn't refetch on `projectId` change while open — **Confirmed**

- **Sources:** OPUS_v2#7
- **Files:** `react/src/components/EnvSettingsModal.tsx:105-132`, `react/src/components/EnvSettings.tsx:29`
- **Validation:** Fetch effect at line 124-132 depends only on `[isOpen]` via `fetchEnvironmentRef`. Original `EnvSettings` used `[isOpen, fetchEnvironment]` where callback captured `[projectId]`. Now `EnvSettings` creates fresh `loadEntries` closure each render, `fetchEnvironment` updates via ref at line 120-121, but while modal stays `isOpen=true` and parent renders with different `projectId`, no fetch is triggered — stale previous project's env remains.
- **Fix:** include `projectId`/`loadEntries` in trigger or add effect on `projectId` when `isOpen`.

### 3.12 `.env` keys with `.` or `-` accepted by validation but unparsable on next upload — **Confirmed**

- **Sources:** SONET_v1#8
- **Files:** `react/src/utils/envFile.ts:24` (`ENV_KEY_RE`), `react/src/utils/envFile.ts:41-42` (`KEY_VALUE_RE`/`KEY_ONLY_RE`), `demetra/api/projects.py:34`
- **Validation:** Backend/frontend `ENV_KEY_RE = ^[A-Za-z_][A-Za-z0-9_.-]*$` allows `.` and `-`; but `.env` parser at lines 41-42 only `([A-Za-z_][A-Za-z0-9_]*)` — rejects dot/dash, so a renamed key `APP.VERSION` is accepted then silently dropped on re-import (`parseEnvFile` yields no entry for that line).
- **Fix:** align regexes (either forbid `.-` in validation or widen parser).

### 3.13 `.env` upload path skips key-length validation used elsewhere — **Confirmed (qualified)**

- **Sources:** SONET_v2#13
- **Files:** `react/src/components/EnvSettingsModal.tsx:229-271`
- **Validation:** `handleUpload` at line 235 calls `upsertEntry(fileEntry.key, ...)` without `validateEnvKey`, unlike `handleAddEntry`/`handleSaveEdit`. The parser already rejects malformed keys using a stricter key regex, so malformed keys do not normally reach this handler. Overlength keys are still accepted by the parser and sent to the backend, which rejects them with a 400 instead of the normal client-side validation UX.
- **Fix:** validate each `fileEntry.key` with `validateEnvKey`.

---

## 4. Already fixed / Not in current HEAD

### 4.1 `MAX_REVIEW_FIXES_ATTEMPTS` dead config / no retry — **Fixed**

- **Sources:** OPUS_v1#8, SONET_v1#9
- **Validation:** A search limited to production source, excluding audit documentation, returns zero hits for `MAX_REVIEW_FIXES`. `demetra/settings.py` currently defines `MAX_BUILD_ATTEMPTS`, `MAX_REVIEW_ATTEMPTS`, `MAX_RESEARCH_ATTEMPTS`, etc., but no `MAX_REVIEW_FIXES_ATTEMPTS`. Finding was valid at review snapshot but the constant has since been removed (or never merged). `run_review_fixes_workflow` single-pass behavior remains, but the dead env var is gone.

### 4.2 Redundant re-fetch in `approve_waitlist_entry` — **Fixed**

- **Sources:** OPUS_v1#10
- **Validation:** At review time the function fetched `find_waitlist_entry_by_id(entry_id)` twice; current code at `demetra/services/auth/waitlist.py:194` fetches once into `entry` and reuses it. Second fetch removed.

---

## 5. Checked and false-positive / intentional

The following were reviewed and confirmed *not* bugs in HEAD:

- Encrypted-secret preservation via `_resolve_encrypted_env_value` / `_fetch_stored_encrypted_value` correctly targets shared `project_environment` table for both project and user scopes; rename ordering (upsert-new-then-delete-old) preserves ciphertext when the happy path succeeds.
- Migration chain `e7f8a9b0c1d2 → e5f6a7b8c9d0` is single-headed and matches `tables.py`.
- Watcher `in_progress` re-application is intentional/idempotent per docstring.
- `api.ts` `202`-before-`!response.ok` ordering is correct.
- All callers of `authenticate_user`/`signup_with_password` handle `WaitlistedError` before generic `AuthError`.
- `react/src/App.css` `.session-search {display:none}` outside mobile media query is intentional per `wiki/pages/2026-09-02-mobile-template-react-frontend.md` ("mobile-only search").

---

## 6. Consolidated remediation priority

| Priority | # | Finding | Lines |
|----------|---|---------|-------|
| **P0 — fix before merge** | 1.1 | IndexError crash after push | `review_fixes.py:95,285` |
|  | 1.2 | Masked `text` secret overwritten with `********` | `EnvSettingsModal.tsx:134, database.py:1861` |
|  | 1.3 | Blank encrypted stores empty ciphertext | `database.py:1685, EnvSettingsModal.tsx:299` |
|  | 1.4 | Whitespace overwrite | `EnvSettingsModal.tsx:179, database.py:1679` |
|  | 2.1 | Rename duplicate/clone | `database.py:1618, EnvSettingsModal.tsx:206` |
|  | 2.2 | Review threads GraphQL failures & truncation | `github.py:149,228` |
|  | 2.4 | Approval ordering/atomicity | `waitlist.py:200` |
|  | 2.5 | Revoked user stuck | `waitlist.py:84` |
|  | 2.6 | Research orphaned branch | `main.py:117, git.py:66` |
| **P1 — next iteration** | 2.3 | Build-agent commit→lost fix | `review_fixes.py:261` |
|  | 2.7 | 500 on audit write | `sessions.py:62,125` |
|  | 3.1 | `entry_id` not in 202 body | `responses.py:19` |
|  | 3.7 | oauth cookie not cleared | `api/github.py:52,82` |
|  | 3.5 | inert stuck | `App.tsx:130` |
|  | 3.6 | stale waitlist banner | `PasswordAuthForm.tsx:79` |
| **P2 — polish** | 3.2 | dead 403 branches | `api/auth.py:79` |
|  | 3.8 | facade unvalidated export | `services/auth/__init__.py:22` |
|  | 3.9 | duplicated env constants | `api/projects.py:34` |
|  | 3.10 | session-dot colors | `App.css:978` |
|  | 3.11 | modal no refetch on projectId | `EnvSettingsModal.tsx:124` |
|  | 3.12 | dot/dash env key vs parser | `envFile.ts:24,41` |
|  | 3.13 | upload skips validation | `EnvSettingsModal.tsx:229` |
|  | 3.3 | unbounded waitlist growth (rate limit) | `sessions.py:46` |
|  | 3.4 | agents missing project_id | `agents/opencode.py:35,276` |

---

## 7. Traceability matrix (48 → 26)

| Group | Merged finding | Original IDs |
|-------|---------------|--------------|
| 1.1 | IndexError whitespace | OPUS_v2#1, SONET_v1#1, SONET_v2#4 |
| 1.2 | Masked text overwrite | SONET_v2#1 |
| 1.3 | Blank encrypted empty secret | OPUS_v1#2, SONET_v1#2, SONET_v2#2; SONET_v1#3 (placeholder) same family |
| 1.4 | Whitespace overwrite | SONET_v1#4 |
| 2.1 | Rename clone/duplicate | SONET_v1#6, SONET_v1#7, SONET_v2#3 |
| 2.2 | gh -F / swallow / truncation / general reviews | OPUS_v1#1, OPUS_v1#5, SONET_v1#5, SONET_v1#15, SONET_v2#7 |
| 2.3 | Build-agent commit lost | OPUS_v1#4 |
| 2.4 | Approval ordering/atomic/pending | OPUS_v1#3, OPUS_v2#2, SONET_v2#10 |
| 2.5 | Revoked stuck | OPUS_v2#3, SONET_v1#11, SONET_v2#11 |
| 2.6 | Research orphaned branch | SONET_v2#5 |
| 2.7 | Audit 500 | SONET_v2#6 |
| 3.1 | entry_id dropped | OPUS_v2#6, SONET_v2#9 |
| 3.2 | Dead 403 | OPUS_v2#4, SONET_v1#13, SONET_v2#14 |
| 3.3 | Unbounded waitlist | OPUS_v1#6 |
| 3.4 | Research missing project_id | OPUS_v1#7 |
| 3.5 | inert stuck | SONET_v1#10, SONET_v2#12 |
| 3.6 | Stale waitlist banner | SONET_v1#12, SONET_v2#15 |
| 3.7 | oauth_state lost | SONET_v1#14 |
| 3.8 | Facade unvalidated | SONET_v2#8 |
| 3.9 | Env key duplication | OPUS_v1#9, OPUS_v2#5 |
| 3.10 | Session dot missing | OPUS_v1#11 |
| 3.11 | Modal no refetch | OPUS_v2#7 |
| 3.12 | dot/dash vs parser | SONET_v1#8 |
| 3.13 | Upload skips validation | SONET_v2#13 |
| 4.1 | MAX_REVIEW_FIXES dead | OPUS_v1#8, SONET_v1#9 |
| 4.2 | Redundant re-fetch | OPUS_v1#10 |

---

## 8. Revalidation baseline

- Python test suite: `967 passed`.
- React test suite: `61 passed`; existing React `act(...)` warnings remain in session-list and app smoke tests.
- React production build: passed (`tsc && vite build`).
- Alembic migration graph: one head, `e7f8a9b0c1d2`.
- Passing tests do not invalidate the active findings above; the affected edge cases currently lack regression coverage.
