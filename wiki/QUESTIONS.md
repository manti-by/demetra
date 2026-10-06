# demetra Wiki — Open Questions

Questions raised by the Consistency Agent when wiki pages disagree and the discrepancy could not
be resolved from the codebase, connected MCPs, or other data sources. A human answers inline in
the **Answer** field; on its next run the Consistency Agent applies the answer to the affected
pages and moves the entry to **Resolved**.

## Open

### Q-002 — MAX_RUN_ATTEMPTS / MAX_PLAN_ATTEMPTS defaults dropped in settings refactor

- **Date:** 2026-10-06
- **Pages:** [[2026-06-08-max-run-attempts-for-a-ticket]], [[2026-06-02-plan-loop-resolve-questions]], [[2026-07-21-rich-markuperror-and-run-attempts]]
- **Discrepancy:** [[2026-06-08-max-run-attempts-for-a-ticket]] and [[2026-07-21-rich-markuperror-and-run-attempts]] claim `MAX_RUN_ATTEMPTS` defaults to 5 (bumped 3→5 in `8ffc53b`, 2026-07-20); [[2026-06-02-plan-loop-resolve-questions]] claims `MAX_PLAN_ATTEMPTS` defaults to 30. Current `demetra/settings.py:46-48` reads `"run": env_get_int("MAX_RUN_ATTEMPTS", 3)` and `"plan": env_get_int("MAX_PLAN_ATTEMPTS", 10)` — commit `10ea543` (2026-09-28, "Refactor settings, cleanup repo") reset both when moving to the `MAX_ATTEMPTS` dict, with no recorded intent.
- **Checked:** `git log -S 'MAX_RUN_ATTEMPTS'` (only `ab2f40a` default 3, `8ffc53b` 3→5, `10ea543` 5→3), `git log -S 'MAX_PLAN_ATTEMPTS'` (`74e8e3f` default 30, `10ea543` 30→10), current `demetra/settings.py:46-48`. Code archaeology confirms the reset happened but not whether it was intentional tuning or an accidental revert to pre-`8ffc53b` values.
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
