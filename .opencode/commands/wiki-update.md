---
name: Create or update a wiki page
description: Create or update the wiki page for the current session - every invocation
in the same session writes to the same file.
agent: build
---

You are the OpenWiki Page Writer for the current session. Each OpenCode session
gets exactly **one** wiki page under `wiki/pages/`. Every `/wiki-update`
invocation within the same session must update that same file — never create a
new one, unless this session has no page yet.

If `wiki/pages/` does not exist (a fresh scaffold ships only the four meta
files), create it first and treat it as an empty page set.

## 1. Resolve this session's existing page

Before writing anything, locate the page that belongs to this session by
inspecting **all three sources** below and collecting the candidates each
produces — do not stop at the first hit:

1. **Your own conversation.** If you have already run `/wiki-update` in this
   session, the absolute path of the file you wrote is in your prior tool
   results. If that file still exists under `wiki/pages/`, it is a candidate.
2. **Frontmatter scan.** Walk every `.md` file under `wiki/pages/` and read
   each file's YAML frontmatter. Match on `session_id:` equal to the current
   session's id (the `sessionID` of the command invocation, e.g.
   `ses_xxxxxxxx`, visible in the system context). Any match is a candidate.
3. **Mapping file.** Read `wiki/.openwiki-sessions.json` (a flat object
   `{ "<session_id>": "<filename>.md" }`). If your session id is a key,
   validate that the value is a bare filename (no path separators, no `..`)
   and that the file still exists under `wiki/pages/`; only then is it a
   candidate. If the key exists but the file is gone, drop the stale entry
   before continuing.

Then reconcile the collected candidates:

- If the sources name **exactly one** unique page, reuse it verbatim.
- If the sources name **different pages** (e.g. the frontmatter scan and the
  mapping disagree, or your conversation path differs from both), stop and
  report the conflict — never guess which file to update and never silently
  pick one.
- If none of the three sources named a page, this session has no page yet —
  continue to step 2 to **create** one.

The conversation source is the most authoritative, but every source is checked
before selecting so a stale mapping or a repeated session id can never
silently redirect the update to the wrong page.

## 2. Filename (new pages only)

```
wiki/pages/YYYY-MM-DD-3-to-5-word-summary.md
```

For example, `2026-07-14-fix-api-auth-tests.md`. Use today's date
(`date +%F`) and a 3-to-5-word kebab-case summary of the session's main topic.

If a file with that name already exists but its frontmatter `session_id:`
belongs to a different session, do NOT overwrite it — append a deterministic
suffix (`-2`, `-3`, …) until the filename is free.

## 3. Write the report

Read `wiki/TEMPLATE.md` for the full structure and its per-`type` section
presets. Follow the presets for the page's `type` (debug / investigation /
code-review / implementation): require step-by-step fixes, files modified, and
test results only where that type's preset calls for them. Every page must
include:

- Frontmatter with `session_id:` set to your session id, and `date:` set to
  today on creation; preserved on update.
- TL;DR.
- The body sections mandated by the page's `type` in `TEMPLATE.md`.
- **No markdown tables.** Render tabular data as a flat bullet list
  (`- **<key>** — <value>`) for quick-reference content, or as H3-headed
  "card" sections when each row has multiple sub-points. GFM tables don't
  diff cleanly in git, are inaccessible to screen readers, and don't
  reflow on mobile. Code blocks and bullet lists of links are not tables.

When updating an existing page, preserve `session_id:` and `date:` from the
original frontmatter. Prefer appending a new dated section over rewriting the
body — earlier work stays visible. Use the canonical heading
`## Update — YYYY-MM-DD HH:MM` inserted directly before `## Follow-ups`; if a
same-day section already exists, extend it instead of adding another.

## 4. Update the session mapping

After every successful write, refresh `wiki/.openwiki-sessions.json` so the
next `/wiki-update` in this session can find the file via the fallback:

```json
{ "<your_session_id>": "<filename>.md" }
```

Read-modify-write the JSON object. Create the file if it does not exist. Only
store the bare filename (no path). If the file exists but is not valid JSON,
back it up to a **collision-safe** filename first (`.openwiki-sessions.json.bak`,
then `.openwiki-sessions.json.bak2`, … — never overwrite an existing backup),
then recover every mapping that is still salvageable from the invalid input and
keep those alongside this session's entry — do not replace the file with only
the current session. If the content cannot be salvaged, leave the backup for
manual review and note it in your report. Pretty-print with two-space indent
and a trailing newline.

## 5. Update the index

`wiki/INDEX.md` lists pages under `## Pages`, newest first, in this format:

```
- [<title>](pages/<filename>) — <one-line summary> (<date>)
```

- If you created a new page, insert its entry immediately after the
  `_Newest first._` marker line.
- If you updated an existing page, update its existing entry in place (title,
  summary, or date if they changed) but do NOT reorder it.

Report: which file you wrote to (created or updated), and the one-line summary.
