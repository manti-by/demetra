---
name: Merge duplicated wiki pages
description: Find and merge near-duplicate wiki pages (at least ~85% similar,
including exact duplicates), keeping the most recent version.
agent: build
---

You are the Wiki Dedup Agent. Read `wiki/README.md` and `wiki/TEMPLATE.md`
for conventions, then work through every page under `wiki/pages/`.

1. **Read all pages.** Read every `.md` file in `wiki/pages/`. Parse the
   frontmatter (title, date, type, status, session_id, services, tickets,
   tags, related) and the full body for each page.

2. **Pairwise comparison.** Compare every page against every other page once.
   For each pair, assess semantic similarity of the subject matter and content.
   A pair is a **near-duplicate** if they are at least approximately 85%
   similar — covering almost the same session, investigation, or topic from
   the same angle, or one is a different write-up of the same session. This
   includes exact duplicates. Consider overlapping TL;DRs, same session_id (a
   strong signal), nearly identical title/tags, and body content that restates
   the same findings. Distinct pages about different subsystems or different
   sessions are NOT duplicates even if they share tags.

3. **Decide what to merge.** Only auto-merge pairs that are the same session:
   identical `session_id`, or clearly the same session recorded twice. For
   pages from distinct sessions, do NOT merge — instead cross-link the two
   pages: add each to the other's `related` frontmatter **and** add a
   reciprocal body `[[...]]` link on both pages (the consistency agent
   requires the two representations to stay in sync), then move on. If the
   two pages make materially conflicting claims (opposite statuses,
   contradicting facts), do NOT auto-merge: verify which claim is current
   against the codebase/docs first, or file a question in
   `wiki/QUESTIONS.md` and skip the pair.

4. **Merge each eligible pair.** For each near-duplicate pair, pick a
   **survivor** filename and merge the second page into it:
   - Keep the **more recent date** (compare `date:` in frontmatter). If the
     dates are equal, prefer the page with the more complete, more accurate
     content; tie-break deterministically (e.g. lexicographically smaller
     filename). Do NOT infer recency from `session_id`.
   - Survivor filename: use the survivor page's original filename — do NOT
     rename unless both are equally good, in which case use the one whose
     title is more descriptive.
   - Merge frontmatter: keep the survivor's `title`, `date`, `session_id`,
     `type`, `status`, `branch`. Union `services`, `tickets`, `tags`, and
     `related` (deduplicated). When singular fields disagree, keep the value
     from the page whose claims you verified in step 3 and note the choice in
     the body. Remove BOTH the survivor filename and the deleted filename from
     the merged `related` list — a page must not link to itself.
   - Merge body: combine unique body sections from both pages, deduplicating
     identical content. Keep the survivor's TL;DR unless the duplicate's is
     strictly better (more complete, more accurate). Preserve and rewrite
     cross-links (`[[...]]`) from both pages so nothing points at the deleted
     filename.
   - Write the merged page back to the survivor's file path.

5. **Clean up.** Delete the duplicate page file from `wiki/pages/`.

6. **Update metadata.** After each merge, update every wiki file that
   references the deleted page:
   - `wiki/INDEX.md` — remove the deleted entry from `## Pages` and from
     `## By topic`; if the survivor's title or summary changed, update its
     entry in both sections. Keep newest-first order.
   - `wiki/QUESTIONS.md` — point any `**Pages:**` reference at the survivor or
     drop the deleted filename.
   - `wiki/.sessions.json` — redirect every mapping whose value is
     the deleted filename to the survivor; drop any stale entry whose key is a
     different session id but whose value is the survivor filename.
   - Every remaining page — rewrite `related:` frontmatter and body `[[...]]`
     links that reference the deleted filename to point at the survivor (or
     remove them if the content was fully merged).

7. **Repeat** steps 2-6 until no more eligible near-duplicates are found (a
   merged page might now be similar to another page).

Report: how many duplicate pairs were found, which pages were merged (survivor
← deleted), which distinct-session pairs were cross-linked instead, and what
changed in the INDEX.
