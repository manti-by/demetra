# demetra Wiki — Open Questions

Questions raised by the Consistency Agent when wiki pages disagree and the discrepancy could not
be resolved from the codebase, connected MCPs, or other data sources. A human answers inline in
the **Answer** field; on its next run the Consistency Agent applies the answer to the affected
pages and moves the entry to **Resolved**.

## Open

### Q-002 — Watcher polls a single tracker while `ISSUE_TRACKER` is per-project

- **Date:** 2026-09-30
- **Pages:** [[2026-09-30-clickup-issue-tracker-support]], [[2026-09-30-mnt-230-claude-code-harness]]
- **Discrepancy:** `ISSUE_TRACKER` resolves per project / per user (like `AGENT_HARNESS`), but `demetra/watcher.py` runs without a project and polls only the tracker `settings.ISSUE_TRACKER` names. A project overriding `ISSUE_TRACKER=clickup` under a `linear` server default is never picked up by the poller (only by `main.py --project-name` / `--task-id`). Should the watcher poll every distinct tracker among configured projects, or is one tracker per deployment the intended scope?
- **Checked:** `demetra/watcher.py` (`get_todo_issues()` with no environment), `demetra/services/tracker/__init__.py` (`load_environment` needs a `user_id`/`project_id`), `demetra/services/daemons/watcher.py` (per-task env is resolved only after a task is known). The harness page has no equivalent problem because the harness is only consulted inside a workflow run.
- **Answer:** _(human writes here)_

_Newest first. Entry format:_


<!--
### Q-001 — <short title of the discrepancy>

- **Date:** YYYY-MM-DD
- **Pages:** [[<page-a-filename-without-.md>]], [[<page-b-filename-without-.md>]]
- **Discrepancy:** <what the pages claim, and how the claims conflict>
- **Checked:** <sources consulted and why they didn't settle it — codebase paths, MCPs, docs>
- **Answer:** _(human writes here)_
-->

## Resolved

### Q-001 — Default bump axis after 2026-09-08 rework is ambiguous

- **Date:** 2026-09-11
- **Pages:** [[2026-06-25-update-project-version]], [[2026-08-21-mnt-176-bump-version-error]], [[2026-09-08-docstring-mcp-search]]
- **Discrepancy:** [[2026-06-25-update-project-version]] and [[2026-08-21-mnt-176-bump-version-error]] claim the auto-bump always increments the minor version; [[2026-09-08-docstring-mcp-search]] reworks `bump_project_version` to `is_major`/`is_minor`/`is_patch` flags with default `is_patch=True` (so `bump_project_version(target_path)` now bumps patch `1.14.1 → 1.14.2`). The service docstring still says "Every feature/bugfix workflow bumps the minor version and the patch component is reset" and the workflow call site `demetra/workflows/build.py:167` still calls with no flag, silently switching the auto-bump from minor to patch. Which axis is intended?
- **Checked:** `demetra/services/runtime/project.py:331` (signature defaults), `demetra/workflows/build.py:167` (bare call), `demetra/services/runtime/project.py:334` docstring text, and all three wiki pages. The code/docstring/call-site drift is explicit in the 2026-09-08 page's "Version bump rework" section, but the intended default was not recorded in the PR.
- **Answer:** Patch default is intentional — commit `dd4f152` (MNT-171 review fixes, 2026-09-11) reworked `bump_project_version` to `is_patch=True` default and updated `tests/test_project.py` to expect `1.14.1 → 1.14.2`; live version `1.17.3` confirms patch increments. Docstring at `project.py:334` is stale.
- **Resolved:** 2026-09-11 — Verified against codebase (`project.py:331`, `build.py:167`, `dd4f152`). Older pages already carry 2026-09-11 consistency notes marking the minor wording as superseded; docstring drift noted in [[2026-09-08-docstring-mcp-search]] and [[2026-06-25-update-project-version]]. No further wiki edits.

_Newest first. Moved here by the Consistency Agent, with a one-line note of what was applied._
