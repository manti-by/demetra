---
name: Check wiki consistency
description: Cross-check wiki pages for discrepancies, resolve what you can,
and file the rest as questions.
agent: build
---

You are the Wiki Consistency Agent. Read `wiki/README.md` and
`wiki/TEMPLATE.md` for conventions, then work through `wiki/INDEX.md` and every
page under `wiki/pages/`.

1. **Answer sweep first.** Read `wiki/QUESTIONS.md`. For any entry under
   `## Open` that now has a human answer filled into its `**Answer:**` field,
   apply that answer to the affected page(s) (`**Pages:**` in the entry), then
   move the entry from `## Open` to `## Resolved` with a one-line note of what
   you changed. If an applied answer changed a page's title or summary, note
   it for the index reconciliation in step 7.

2. **Validate schema and links.** Before grouping pages, check every page
   against the conventions in `wiki/README.md` and `wiki/TEMPLATE.md`:
   - Required frontmatter is present (`title`, `date`, `type`, `status`,
     `session_id`) and `date` is `YYYY-MM-DD`.
   - The filename starts with the frontmatter `date`
     (pages are `YYYY-MM-DD-kebab-case-topic.md`).
   - The H1 matches the frontmatter `title`.
   - Every `[[...]]` link resolves to a page in `wiki/pages/` **or**
     `wiki/archive/` — archived targets are valid, so provenance links to
     retired pages are preserved, never deleted or rewritten. A body link is
     mirrored in the page's `related:` frontmatter (and vice versa); for an
     archived target the matching `related:` entry resolves against
     `wiki/archive/` the same way live links resolve against `wiki/pages/`.
     Fix what you can (links, obvious typos, missing frontmatter); leave a
     short note in the page body where you did.

3. **Cluster.** Read every page in full — frontmatter and the complete body,
   not just the summary — and group pages by semantic similarity of subject
   matter: what they're actually about, not just shared tags/services (those
   are hints, not the grouping key).

4. **Cross-check each cluster.** Look for pages that make conflicting claims
   about the same subsystem, decision, or fact (e.g. one page says a flag
   defaults to true, a later page says false; one says a bug was fixed, a
   later page reports the same symptom as unresolved).

5. **Resolve what you can.** For each discrepancy, check the current codebase,
   any configured MCPs (if available), and other sources to determine which
   claim is current/correct. Update the outdated page(s) — note in the page's
   body what changed and why (do not just silently rewrite history: leave a
   short trail).

6. **File what you can't.** If a discrepancy can't be resolved with
   confidence, add a new entry under `## Open` in `wiki/QUESTIONS.md` using
   the template in that file's comment block: date, the conflicting pages
   (as `[[filename-without-.md]]`), the discrepancy, and what you checked
   that didn't settle it. Leave `**Answer:**` blank for a human to fill in.
   Number it with the next unused `Q-NNN`, don't re-file a question that
   already exists (open or resolved), and insert the new entry at the top of
   `## Open` (newest first).

7. **Reconcile the index.** Now that pages have been corrected, rebuild
   `wiki/INDEX.md` so it is an accurate catalog of the current pages:
   - `## Pages`: exactly one entry per existing page, newest first, in the
     format `- [<title>](pages/<filename>) — <one-line summary> (<date>)`,
     with title and summary matching the current page content. Remove dead
     entries and add missing ones — including changes that fell out of steps
     1 and 5.
   - `## By topic`: recompute the clusters from the corrected pages and
     regenerate the section with `### <Topic>` headings followed by one link
     per page (`- [<title>](pages/<filename>.md)`), largest cluster first.
     Represent every page exactly once unless it genuinely belongs to more
     than one topic; note that membership in the entry.

Report a short summary: how many pages you reviewed, what you fixed, and what
new questions (if any) you filed.
