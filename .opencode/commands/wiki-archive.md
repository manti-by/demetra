---
name: Archive old wiki pages
description: Archive old wiki pages (default > 3 months) by extracting any
still-useful information into the most relevant current pages, then move the
originals from wiki/pages/ to wiki/archive/.
agent: build
---

You are the OpenWiki Archive Agent. Read `wiki/README.md` and `wiki/TEMPLATE.md`
for conventions, then work through every page under `wiki/pages/`.

Pages are session-scoped — once a session is old enough that the detailed
narrative is no longer the freshest source of truth, distil whatever is **still
useful** (decisions, conventions, stable patterns, external refs) into the most
relevant current page, then retire the original to `wiki/archive/` so the
active `wiki/pages/` stays focused on recent sessions.

The default age threshold is **3 months** (compare each page's `date:` against
`date +%F` today). If the user invokes this command with an explicit age
(e.g. `/wiki-archive 6mo`), respect that override — accept any duration the
user names (`3mo`, `90d`, `6 months`, `1y`, …).

## 1. Discover candidates

1. **Enumerate pages.** Read every `.md` file in `wiki/pages/`. Parse the
   frontmatter of each — you need `date` (the session date), `status`,
   `type`, `services`, `tickets`, `tags`, and `related` at minimum.
2. **Filter by age.** A page is a candidate if its `date` is older than the
   threshold. Pages without a parseable `date` are NOT candidates — log them
   in the report and skip (do not guess; bad data must surface, not be
   silently archived).
3. **Filter by status.** Pages with `status: open` or `status: in-progress`
   are NOT candidates — they are still being actively worked on, and
   archiving them would hide live state. Skip them and note them in the
   report under "needs human review".
4. **Filter by open follow-ups.** If a candidate's body has a `## Follow-ups`
   section with any non-trivial entry (anything other than `- None`), skip
   the page. Live follow-ups must not be silently retired — leave the page
   in `wiki/pages/` and surface it in the report under "needs human review".

The three skip categories in this step are reported separately — never lump
them together.

## 2. Plan the merge

For each remaining candidate:

1. **Read it in full.** Frontmatter and complete body. Note the TL;DR, the
   page's `services` / `tickets` / `tags`, and the topic (from the body, not
   just the frontmatter tags).
2. **Identify the durable content.** Carry forward only:
   - **Decisions / architectural choices** that are still in effect. Prefer
     the original rationale — the most recent page on the same topic may
     not have re-stated it.
   - **Conventions and patterns** that have stuck (e.g. "we use Biome, not
     ESLint").
   - **External service refs / URLs** (vendor docs, Linear tickets, RFCs)
     that other pages still link to or should link to.
   - **Resolved follow-ups** whose resolution is still valid.

   Do NOT carry forward:
   - Step-by-step debug narrative ("we tried X, didn't work, tried Y").
   - Session-specific breadcrumbs (transcript excerpts, specific
     `session_id` cross-references) — these age out by design.
   - Code snippets that have since been superseded. If you carry a snippet
     forward, verify it against the current codebase first; do not paste
     stale code.

3. **Find the target page.** Search `wiki/pages/` for the page that
   currently owns the same topic — the most recent page on the same
   subsystem / service / tag set, with overlapping `services` or `tags`
   in frontmatter, or an explicit `related:` link to the candidate. Pick
   a single best target when one clearly dominates; otherwise pick a small
   set (2–3) of equally good targets and merge into all of them.

   If there is **no good target** (the candidate is a true one-off, or its
   useful info is already fully covered by a newer page), record the
   candidate in the report as "no target — archive without merge" and
   proceed directly to step 5 (no merge, just move).

## 3. Merge into the target

For each (candidate, target) pair:

1. **Insert into the target.** Add a new body section to the target page,
   inserted **immediately before** the target's `## Follow-ups` section,
   with the heading:

   ```
   ## Source — [[<candidate-filename-without-.md>]]
   ```

   Under that heading, copy the useful info distilled in step 2. Quote short
   snippets verbatim; paraphrase long passages. Whenever you carry a
   decision or convention forward, attribute it inline:
   "Originally decided in [[<candidate-filename-without-.md>]] on
   YYYY-MM-DD" — the date lets the reader judge the source's recency.

2. **Update target frontmatter.**
   - Append the candidate's filename to the target's `related:` list
     (and `tickets:`, `tags:`, `services:` — union, deduped, no
     reordering).
   - Do **not** change the target's `date`, `session_id`, `title`, or
     `status`.

3. **Update the candidate's `related:` list (now).** For every other
   page in `wiki/pages/` that currently lists the candidate in its
   `related:` frontmatter (the target, plus any sibling you noticed in
   step 2.3), rewrite the entry to point at the **target**. Do this now
   — step 5 will delete the candidate file and dangling references must
   be gone by then.

4. **Body `[[...]]` cross-links.** For each surviving page in
   `wiki/pages/` that has a body `[[candidate-filename-without-.md]]`
   link, rewrite it to `[[target-filename-without-.md]]`. Mirror the
   change in that page's `related:` frontmatter so the two stay in sync.
   If the candidate was archived without merge, drop the link and the
   `related:` entry instead.

5. **Stamp a "moved to" note on the candidate (only when a merge
   happened).** Just below the candidate's H1, prepend:

   ```
   > **Archived on YYYY-MM-DD.** Useful info merged into
   > [[<target-filename-without-.md>]]. See wiki/archive/ for the
   > original.
   ```

   Use today's date. Skip this note if the candidate was archived
   without merge (step 2.3).

## 4. Per-candidate isolation

Process each candidate independently — a single candidate may merge into
multiple targets, and a single target may absorb multiple candidates.
**Never chain candidates:** every merge must land on a page that will
**remain in `wiki/pages/`** (i.e. is not itself a candidate in this run).
If you find yourself wanting to merge A into B and B is also a candidate,
stop — promote B's content into a third (non-candidate) page first, or
defer A to the next run.

## 5. Move the originals

1. **Create the archive directory** if it does not exist:
   `mkdir -p wiki/archive`.
2. **Move** each candidate from `wiki/pages/<name>.md` to
   `wiki/archive/<name>.md` using `git mv` (so git tracks the rename
   rather than a delete + add). If the destination already exists
   (collision with a previous archive), append a `-2`, `-3`, … suffix
   until the path is free; record the rename in the report.
3. **Update `wiki/.openwiki-sessions.json`.** For each archived candidate,
   if the session-id → filename mapping points at the candidate, redirect
   it to the target page (or remove the entry if archived without merge).
   Leave any other-session-id mapping that happens to point at the
   candidate alone — `wiki-update` cleans those on its next write.

## 6. Update the index

Reconcile `wiki/INDEX.md`:

- `## Pages`: remove every archived page's entry. Do not reorder the
  rest — keep newest-first order intact. If a target's title or summary
  materially changed (rare — only when a merge actually changed what the
  page is about), note it for the consistency agent to revisit on its
  next run.
- `## By topic`: drop archived pages from their clusters. If a cluster
  loses its last page, remove the cluster heading entirely.
- Do **not** add an `## Archive` section — the consistency agent
  maintains the archive catalog, not this command. `wiki/archive/`
  existing on disk is the source of truth.

## 7. Report

Print a short summary at the end:

- How many candidates were considered, and how many were skipped per
  filter in step 1 (bad date / live status / open follow-ups), with one
  line per skip category.
- For each archived page: the candidate filename, the target(s) it
  merged into (or "no target — archived without merge"), and a one-line
  description of what useful info was carried forward.
- The "needs human review" list: any candidates that were skipped
  because of open follow-ups or live status, with the filename and the
  reason.

End with a one-line verdict: `N archived, M skipped, K needs-human-review`.
