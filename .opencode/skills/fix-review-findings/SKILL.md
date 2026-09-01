---
name: fix-review-findings
description: Fix all unresolved review findings on a PR
---

# Fix Review Findings Skill

You fix all unresolved review threads on a pull request. Every thread must be addressed — none may be left unresolved.

## Inputs

You receive a list of unresolved review threads. Each thread contains one or more comments with fields like `body`, `path`, `line`, `diffHunk`, and `author`.

## Steps

1. **Read every thread.** Treat each thread's comments as the ground truth. Do not skip threads by author — any author (bot or human) counts.
2. **Locate the code.** For each thread, open the file at `path` and the surrounding lines (`line`/`diffHunk`). If no path is given, treat it as a general PR comment and still address the concern in the codebase.
3. **Fix the finding.** Edit the source to resolve the concern. Keep fixes focused — do not refactor unrelated code. Match surrounding style from `AGENTS.md`.
4. **Verify.** After all fixes, run the relevant gates (`uv run ruff check .`, `uv run ty check`, `uv run pytest` if present). Fix any failures you introduced.
5. **Stage only.** Stage changes with `git add` per file. Do NOT commit, do NOT push — the orchestrator commits and pushes.

## Output

- A short summary of which threads were addressed and how.
- No markdown tables — use bullet lists.

## Rules

- Fix every unresolved thread, not just the first one.
- Do not resolve threads via API — code fixes resolve them.
- Do not add drive-by refactors, leftover TODOs, or debug prints.
- Keep changes minimal and correct.
