# demetra Wiki — Open Questions

Questions raised by the Consistency Agent when wiki pages disagree and the discrepancy could not
be resolved from the codebase, connected MCPs, or other data sources. A human answers inline in
the **Answer** field; on its next run the Consistency Agent applies the answer to the affected
pages and moves the entry to **Resolved**.

## Open

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

### Q-002 — Three overlapping ANSI stripping pages

- **Date:** 2026-07-20
- **Pages:** [[2026-07-20-resolve-ansi-color-escape-codes-in-logs]], [[2026-07-20-log-coloring-issue]], [[2026-07-20-colors-fix]]
- **Discrepancy:** Three pages document the same ANSI stripping fix with different detail levels and slightly different scope counts (3 vs 4 levels). Duplicate coverage of the same session — should they be consolidated into one canonical page?
- **Checked:** All three pages describe the same code changes (AnsiStrippingFilter, live_stream, settings.py dictConfig, setup_session_logging). No conflicting claims, just redundant documentation.
- **Answer:** Consolidated by Dedup Agent: survivor [[2026-07-20-resolve-ansi-color-escape-codes-in-logs]] (most descriptive title, latest session_id). Merged tags from all three pages. Other two pages deleted.
