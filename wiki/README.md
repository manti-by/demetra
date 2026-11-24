# Demetra Wiki

A persistent, compounding knowledge base for this project. Each page captures **one session** -
a debugging chase, a code review, an investigation into how something works, or a set of changes
- so the reasoning survives after the terminal scrollback is gone.

Inspired by [Karpathy's LLM-maintained wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
the human curates and directs; the agent does the bookkeeping (writing pages, cross-linking,
keeping the index current). Pages are plain Markdown so they stay human-readable and diff cleanly in git.

## Layout

- `README.md` - This file - conventions (the "schema").
- `TEMPLATE.md` - The one unified page template. Copy it to start a page.
- `INDEX.md` - Catalog of every page with a one-line summary. Kept current on each new page.
- `QUESTIONS.md` - Open questions from the Consistency Agent about wiki discrepancies, awaiting a human answer.
- `pages/YYYY-MM-DD-<topic>.md` - The pages themselves.

## How a page gets written

Two paths produce the same file:

- **Session end (automatic)** - `demetra/workflows/cleanup.py` calls
  `write_session_wiki_page`, which gathers the deterministic facts (git diff, build plan,
  session log tail, ticket) and hands them to the LLM via `compose_wiki_page`
  (`demetra/services/llm/openrouter.py`, prompt `demetra/prompts/compose_wiki_page.md`).
  The LLM authors the entire body from the first `##` heading down. The frontmatter, the
  H1, the filename and the `INDEX.md` entry stay deterministic, so pages remain
  machine-queryable. There is no scaffold fallback: if the LLM call fails the session
  commits without a page and the failure is logged.
- **In-session (`/wiki-sync`)** - the `wiki-sync` skill has the build agent write the page
  by hand, following `TEMPLATE.md` and the conventions below.

Both paths are bound by the same rules, so a session-written page and a hand-written page
are indistinguishable in shape.

## Naming convention

```
pages/YYYY-MM-DD-kebab-case-topic.md
```

- Date-prefixed so pages sort chronologically and filenames stay unique.
- `topic` is a short kebab-case slug of the subject (e.g. `multi-agent-plan-step`, `composite-command`).
- Meta files (`README.md`, `TEMPLATE.md`, `INDEX.md`, `QUESTIONS.md`) are **not** date-prefixed.

## Page types

Every page declares a `type` in its frontmatter. The template lists the recommended sections for each:

- `debug` - Chasing a symptom to a root cause. Symptom -> steps -> root cause -> fix.
- `investigation` - Understanding how a subsystem works / where a gap is. No single fix.
- `code-review` - Findings against a diff or branch. Numbered findings + summary table.
- `implementation` - A set of changes that were made. Steps with before/after + test results.

## Frontmatter

`wiki/pages/` and `wiki/archive/` form a single [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
bundle. Every page starts with YAML frontmatter (see `TEMPLATE.md`), which makes the wiki
machine-queryable — you can grep for a ticket, a service, or a tag across all pages.

- `title`, `generated`, `description`, `type`, `status`, `session_id` - always set; `generated` is
  `{by: demetra, at: <ISO 8601 UTC timestamp>}` and replaces the old `date` field.
- `status` uses the OKF lifecycle values `stable`, `draft` or `deprecated`; pages in
  `wiki/archive/` are `deprecated`.
- `services`, `branch`, `tickets`, `tags` - set what applies; leave empty (`[]` / `-`) otherwise.
- `related` - filenames of pages this one links to. Keep it in sync with the standard markdown
  links in the body.

Formatting is fixed so pages diff cleanly against each other and against what
`demetra/services/wiki/render.py` writes:

- List fields (`services`, `tickets`, `tags`, `related`) use **inline YAML flow style on one
  line** - `services: [api, react]` - never block style (`services:` followed by `- item` lines).
  Empty means `[]`, never a blank value.
- One space after each `:`; no column alignment padding.
- Quote values only when YAML requires it: `branch: "-"` (a bare `-` is null), or a tag that would
  otherwise parse as a number or bool (`'403'`, `'true'`).
- `dump_frontmatter` is the reference implementation - a service-written page and a hand-written
  page must be byte-identical in shape.

## Cross-linking

Link related pages inline with an absolute bundle-relative markdown link
(`[2026-07-09-otel-ssl-cert-debug](/pages/2026-07-09-otel-ssl-cert-debug.md)`). Pages that now live
in `wiki/archive/` use `/archive/<filename>.md` instead. Mirror the targets in the `related:`
frontmatter list. Cross-links are what turn a folder of notes into a knowledge graph - always link
back to prior pages on the same subsystem.

The one-time validator/migrator is `uv run python -m demetra.services.wiki.okf --dry-run` (drop
`--dry-run` to write). It reports pages that fail OKF validation and rewrites them through
`dump_frontmatter`, so hand-written pages should match that serializer's shape.
