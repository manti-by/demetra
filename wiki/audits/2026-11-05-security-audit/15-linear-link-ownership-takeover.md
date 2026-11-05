# 15 — Linear-link ownership takeover via session upsert

## Summary

- **Title:** A user-editable Linear link can transfer an existing session's owner
- **Problem:** The watcher derives session ownership from globally collected,
  user-editable Linear project links (`get_linked_projects`), and `process_tasks`
  upserts that derived identity. `upsert_pending_session`'s `ON CONFLICT (task_id)`
  update replaces an existing session's `project_id`/`user_id`, allowing another
  project owner to acquire private session data and deletion authority.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-863** · **Category:** authorization_bypass
- **CodeRabbit ID:** `2ff09833-6598-43f3-aa0d-786a357744fe`
- **Files (current):** `demetra/services/linear/tasks.py:8-27` (`get_linked_projects`),
  `demetra/services/linear/tasks.py:103-121`, `demetra/services/daemons/watcher.py:198-210`,
  `demetra/services/persistence/database.py:221-234` (`upsert_pending_session`)
- **Revalidation:** Confirmed. `get_linked_projects` maps both `linear_project_id` and
  `name` to `(project_id, user_id)`, and the `ON CONFLICT ... DO UPDATE SET
  project_id = COALESCE(EXCLUDED.project_id, sessions.project_id), user_id =
  COALESCE(EXCLUDED.user_id, sessions.user_id)` overwrites a non-null owner.

## Steps

1. Reserve and validate Linear project bindings before using them as ownership: ensure a
   `linear_project_id` maps to exactly one project and that the owning user matches the
   authenticated owner.
2. In `upsert_pending_session`, stop silently overwriting ownership: when an existing
   session already has a non-null `project_id`/`user_id` that differs from the incoming
   value, reject the upsert (or raise) instead of `COALESCE`-overwriting.
3. Introduce an explicit, authorized transfer path (admin-only) for legitimately
   changing a session's owner; never allow a routine task refresh to transfer ownership.
4. Add tests: a conflicting task refresh is rejected; a task refresh with the same owner
   still succeeds.
