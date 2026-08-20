---
name: Update AGENTS.md
description: Revalidate AGENTS.md against the current codebase, wiki pages,
and git log; auto-apply fixes and print a diff summary.
agent: build
---

You are the AGENTS.md Maintenance Agent. Re-validate `AGENTS.md` so it stays
an accurate map of this repo. **Update only `AGENTS.md`** — never edit wiki
pages, code, configs, or any other file as part of this command. The user
reviews the resulting diff in git.

**Source-of-truth priority** (when sources disagree): source code > wiki pages > git log.

1. **Read the current map.** Read `AGENTS.md` end-to-end. Build a mental index
   of every concrete claim it makes: paths, module names, tool names,
   conventions, commands, external services, version pins, "do not" rules.

2. **Scan the wiki.** Read `wiki/INDEX.md`, then skim every entry it links
   under `wiki/pages/`. Read deeper into a page only when it touches an
   AGENTS.md section you're auditing. Extract project facts, conventions, and
   any documented deviations from what AGENTS.md currently says.

3. **Scan the code.** For every concrete claim in AGENTS.md, verify it
   against the actual repository:
   - Paths and module names — `Glob` or `ls` to confirm existence and
     location.
   - File purposes — read the file's docstring / top-of-file to confirm role.
   - Tooling, linters, type checkers, Python version, dependency lists — read
     `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml` (and equivalents).
   - Naming and architecture rules — sample a few files per layer
     (`demetra/library/`, `demetra/services/`, `demetra/workflows/`,
     `demetra/api/`, `demetra/tools/`).
   - The "Do NOT use" list — `grep` for the forbidden patterns to confirm
     they really are forbidden and the list is complete.

4. **Scan git log.** Run `git log --oneline -100` plus targeted
   `git log --stat -- <path>` for the paths AGENTS.md mentions
   (`demetra/`, `tests/`, `pyproject.toml`, `.opencode/`, `migrations/`).
   Look for renames, new modules, dropped tools, version bumps, and
   convention changes that haven't been folded into AGENTS.md yet.

5. **Classify drift** into three buckets:
   - **Stale** — a claim in AGENTS.md is no longer true (path moved, tool
     renamed, convention changed, version bumped).
   - **Missing** — a fact documented in code or the wiki has no entry in
     AGENTS.md (new module, new external dep, new convention).
   - **Wrong** — a factual error (broken path, dead link, mis-stated rule,
     bad count, wrong default).

   For each finding, record: AGENTS.md section, the conflict, the
   source-of-truth citation (file + line, wiki page, or commit SHA), and the
   proposed fix.

6. **Update AGENTS.md.** Apply every fix in place. Preserve the existing
   section order, heading style, and voice. Keep the file readable — do not
   turn it into a changelog. If a section grows large, prefer a tight bullet
   list over prose. Do not invent facts that aren't supported by code, wiki,
   or git.

7. **Print a diff summary.** Show what changed, grouped by the three
   buckets above. For each fix, cite the source of truth that justified it
   (e.g. `demetra/foo.py:12`, `wiki/pages/2026-07-23-...md`, commit SHA).
   End with a one-line verdict: `N stale, M missing, K wrong → AGENTS.md
updated` (or `no drift detected` if nothing changed).

If a discrepancy can't be resolved confidently (e.g. code and wiki
contradict each other with no git history to settle it), do not guess — note
it in the summary as `needs human decision` and leave AGENTS.md untouched
for that item.
