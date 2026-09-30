---
name: fix-review-findings
description: Fix every unresolved review thread on a pull request — fetches unresolved comments via the GitHub CLI if not already supplied, applies a code fix per thread, then verifies with ruff/ty/pytest. Triggered by "fix review findings", "fix review comments", "address PR feedback", "resolve review threads".
---

# Fix Review Findings

Fix all unresolved review threads on a pull request. Every thread must be addressed — none may be left unresolved.

## Inputs

If the user already supplied a list of unresolved review threads (each with `body`, `path`, `line`, `diffHunk`, `author`), use that list directly and skip to Steps.

Otherwise, fetch them yourself:

1. Resolve the PR: use the number/URL the user gave, or infer it from the current branch with `gh pr view --json number,url`.
2. Fetch unresolved review threads via the GraphQL API (`gh pr view` alone does not expose thread resolution state):

   ```bash
   gh api graphql -f query='
     query($owner:String!,$repo:String!,$number:Int!){
       repository(owner:$owner,name:$repo){
         pullRequest(number:$number){
           reviewThreads(first:100){
             nodes{
               isResolved
               comments(first:50){nodes{body path line diffHunk author{login}}}
             }
           }
         }
       }
     }' -f owner=<org> -f repo=<repo> -F number=<pr_number>
   ```

   Filter to `isResolved == false`. Also pull plain (non-threaded) PR-level comments via `gh pr view <number> --json comments` and treat each as a general finding.

## Steps

1. **Read every thread.** Treat each thread's comments as ground truth. Do not skip threads by author — bot or human, all count.
2. **Locate the code.** For each thread, open the file at `path` and the surrounding lines (`line`/`diffHunk`). If no path is given, treat it as a general PR comment and still address the concern in the codebase.
3. **Fix the finding.** Edit the source to resolve the concern. Keep fixes focused — do not refactor unrelated code. Match this repo's conventions (AGENTS.md).
4. **Verify.** After all fixes, run the relevant gates: `uv run ruff check .`, `uv run ty check`, and `uv run pytest tests/ -q` if tests are present. Fix any failures you introduced.
5. **Stage only.** Stage changes with `git add <file>` per file. Do NOT commit and do NOT push unless the user explicitly asks — there is no orchestrator here to hand that off to.

## Output

- A short summary of which threads were addressed and how.
- No markdown tables — use bullet lists.

## Rules

- Fix every unresolved thread, not just the first one.
- Do not resolve threads via the API — a code fix addressing the concern is what resolves them (or ask the user whether to mark them resolved).
- Do not add drive-by refactors, leftover TODOs, or debug prints.
- Keep changes minimal and correct.
