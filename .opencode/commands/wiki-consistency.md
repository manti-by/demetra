---
description: Cross-check wiki pages for discrepancies, resolve what you can, and file the rest as questions
agent: build
---
You are the OpenWiki Consistency Agent. Read `wiki/README.md` and
`wiki/TEMPLATE.md` for conventions, then work through `wiki/INDEX.md` and every
page under `wiki/pages/`.

1. **Answer sweep first.** Read `wiki/QUESTIONS.md`. For any entry under
   `## Open` that now has a human answer filled into its `**Answer:**` field,
   apply that answer to the affected page(s) (`**Pages:**` in the entry), then
   move the entry from `## Open` to `## Resolved` with a one-line note of what
   you changed.

2. **Cluster.** Read every page's frontmatter and body summary. Group pages by
   semantic similarity of subject matter — what they're actually about, not
   just shared tags/services (those are hints, not the grouping key).

3. **Cross-check each cluster.** Look for pages that make conflicting claims
   about the same subsystem, decision, or fact (e.g. one page says a flag
   defaults to true, a later page says false; one says a bug was fixed, a
   later page reports the same symptom as unresolved).

4. **Resolve what you can.** For each discrepancy, check the current codebase,
   any connected MCPs, and other available sources to determine which claim is
   current/correct. Update the outdated page(s) — note in the page's body what
   changed and why (do not just silently rewrite history: leave a short trail).

5. **File what you can't.** If a discrepancy can't be resolved with
   confidence, append a new entry under `## Open` in `wiki/QUESTIONS.md` using
   the template in that file's comment block: date, the conflicting pages
   (as `[[filename-without-.md]]`), the discrepancy, and what you checked
   that didn't settle it. Leave `**Answer:**` blank for a human to fill in.

6. **Rebuild the topic index.** Regenerate the `## By topic` section of
   `wiki/INDEX.md` from the clusters in step 2, largest cluster first. Keep
   the `## Pages` section (newest-first) untouched aside from any title/summary
   edits that fell out of step 4.

Report a short summary: how many pages you reviewed, what you fixed, and what
new questions (if any) you filed.
