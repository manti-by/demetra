# demetra Wiki — Open Questions

Questions raised by the Consistency Agent when wiki pages disagree and the discrepancy could not
be resolved from the codebase, connected MCPs, or other data sources. A human answers inline in
the **Answer** field; on its next run the Consistency Agent applies the answer to the affected
pages and moves the entry to **Resolved**.

## Open

### Q-001 — Default bump axis after 2026-09-08 rework is ambiguous

- **Date:** 2026-09-11
- **Pages:** [[2026-06-25-update-project-version]], [[2026-08-21-mnt-176-bump-version-error]], [[2026-09-08-docstring-mcp-search]]
- **Discrepancy:** [[2026-06-25-update-project-version]] and [[2026-08-21-mnt-176-bump-version-error]] claim the auto-bump always increments the minor version; [[2026-09-08-docstring-mcp-search]] reworks `bump_project_version` to `is_major`/`is_minor`/`is_patch` flags with default `is_patch=True` (so `bump_project_version(target_path)` now bumps patch `1.14.1 → 1.14.2`). The service docstring still says "Every feature/bugfix workflow bumps the minor version and the patch component is reset" and the workflow call site `demetra/workflows/build.py:167` still calls with no flag, silently switching the auto-bump from minor to patch. Which axis is intended?
- **Checked:** `demetra/services/runtime/project.py:331` (signature defaults), `demetra/workflows/build.py:167` (bare call), `demetra/services/runtime/project.py:334` docstring text, and all three wiki pages. The code/docstring/call-site drift is explicit in the 2026-09-08 page's "Version bump rework" section, but the intended default was not recorded in the PR.
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

_Newest first. Moved here by the Consistency Agent, with a one-line note of what was applied._
