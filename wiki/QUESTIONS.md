# demetra Wiki — Open Questions

Questions raised by the Consistency Agent when wiki pages disagree and the discrepancy could not
be resolved from the codebase, connected MCPs, or other data sources. A human answers inline in
the **Answer** field; on its next run the Consistency Agent applies the answer to the affected
pages and moves the entry to **Resolved**.

## Open

_Newest first. Entry format:_

### Q-001 — Session step `validate` set by build workflow but absent from `StepType` enum

- **Date:** 2026-08-06
- **Pages:** [[2026-08-05-post-build-validation]], [[2026-06-08-session-step-attribute]], [[2026-07-16-fix-step-status-review-findings]]
- **Discrepancy:** `2026-08-05-post-build-validation.md` says the session step is set to
  `validate` before the validate-agent runs (`update_session_step(..., step="validate")`), and
  `demetra/workflows/build.py:102` does write `step="validate"`. But `StepType` in
  `demetra/library/models.py:8-9` lists only `initial/plan/build/review/lint/test/push/completed/failed/awaiting_input`
  — no `validate` — so `VALID_STEPS = set(get_args(StepType))` (`demetra/api/sessions.py:20`)
  rejects `validate` as a session-list filter, and older pages (`session-step-attribute`,
  `fix-step-status-review-findings`) document a step vocabulary that never included it.
- **Checked:** `demetra/library/models.py` (StepType literal), `demetra/workflows/build.py:102`
  (`step="validate"`), `demetra/api/sessions.py:20-33` (VALID_STEPS validation),
  `git log --all -S"validate" -- demetra/library/models.py` (no commit ever added `validate`
  to the enum). Codebase, not a wiki-vs-wiki conflict.
- **Answer:** _(human writes here)_

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
