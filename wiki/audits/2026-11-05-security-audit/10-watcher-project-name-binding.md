# 10 — Watcher selects project by display name, not resolved id

## Summary

- **Title:** Task dispatched by Linear display name can run in another tenant's context
- **Problem:** `get_todo_issues` resolves a task's local `project_id`/`user_id`, but
  `process_tasks` discards that identity and enqueues the workflow with the
  independently controlled Linear *display name*. `setup_workflow` then selects a
  project globally by name and loads its decrypted credentials without verifying that
  the task and session belong to it, allowing one project's task to run against another
  owner's repository and environment.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-863** · **Category:** authorization_bypass
- **CodeRabbit ID:** `79d461b1-214d-426d-a30b-0cddc0911de3`
- **Files (current):** `demetra/services/daemons/watcher.py:177-223` (`process_tasks`),
  `demetra/services/daemons/watcher.py:78-161` (`run_workflow`),
  `demetra/workflows/setup.py` (`setup_workflow`)
- **Revalidation:** Confirmed. `process_tasks` uses `task.project_id`/`task.user_id` for
  the upsert but calls `delay_run_workflow(project_name=task.project_name, ...)`, and
  `run_workflow` launches `main.py --project-name <name>`.

## Steps

1. Queue the immutable resolved identity: change `delay_run_workflow` /
   `run_workflow` (and `enqueue_workflow`) to carry `project_id` (and `user_id`) in
   addition to, or instead of, the display name.
2. Launch `main.py` with `--project-id <id>` (plus a task id) so `setup_workflow`
   selects the project by id rather than by global name search.
3. In `setup_workflow` (`demetra/workflows/setup.py`), before loading environments or
   touching the checkout, verify the fetched task and any persisted session both
   reference that exact `project_id` and owner.
4. Reject a run when the resolved `project_id` is `None` (no linked project) instead of
   falling back to a name lookup.
5. Add tests: a task whose name collides with another owner's project is rejected /
   bound to the correct project id.
