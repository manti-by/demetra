# Prompts Report GPT-5.5

## Summary

The prompt set is generally concise and focused, especially the extraction prompts. The main improvement areas are conflict-resolution ambiguity, missing read-only safeguards for review/research prompts, underspecified output formats, and inconsistent handling of questions between plan summarization and question extraction.

## Findings

1. `rebase_agent.md`
   The conflict preference is likely confusing. During `git rebase`, Git's `ours` and `theirs` semantics are inverted compared with merge. The prompt says to prefer the branch being rebased onto, but labels it `theirs/base branch`, which may cause the agent to choose the wrong side. Clarify the exact desired side without relying on `ours` or `theirs` unless verified.

2. `merge_agent.md`
   `theirs/base branch` is ambiguous. In this workflow, `origin/{base_branch}` is merged into the feature branch, so the intended preference should be stated explicitly as “prefer the incoming base branch version.”

3. `merge_agent.md` and `rebase_agent.md`
   Add conflict-resolution safeguards: inspect each conflicted file before editing, remove all conflict markers, avoid unrelated files, stage only resolved conflict files, and verify the result if possible.

4. `rebase_agent.md`
   Keep `Do NOT run git rebase --continue` prominent. The service performs `git rebase --continue` after the agent stages resolved files.

5. `resolve_questions.md`
   The prompt should explicitly be read-only. Add instructions not to edit files, stage changes, commit, push, or run destructive commands.

6. `resolve_questions.md`
   Add a strict answer format so downstream consumers get consistent output. Suggested format:

   ```md
   1. Question: ...
      Answer: ...
      Evidence: path:line-line, symbol
   ```

7. `analyze_ticket.md`
   The JSON schema defines `technical_requirements` and `acceptance_criteria` as strings, but the guidelines ask for lists. Prefer JSON arrays for these fields, or explicitly require newline-delimited strings.

8. `analyze_ticket.md`
   “Make reasonable assumptions” can fabricate requirements. Safer behavior is to use an empty value, `null`, or clearly mark inferred information.

9. `analyze_ticket.md`
   Project name fallback is undefined. The prompt lists `ODIN`, `Demetra`, and `Coruscant`, but does not say what to do when no project is clear. Add a deterministic fallback.

10. `summarize_plan.md`
    It asks to include questions at the end, but questions are extracted separately by `extract_questions.md`. This can duplicate or reintroduce unresolved questions into the build plan. Consider excluding questions from the summarized build plan entirely.

11. `summarize_plan.md`
    Add extraction-only constraints: do not invent files, implementation steps, requirements, or technical decisions not present in the plan output.

12. `generate_pr_description.md`
    The output is underspecified. Add a concrete PR body template such as `Summary`, `Changes`, and `Testing`, and define what to do when testing information is unavailable.

13. `review_agent.md`
    “Check git staged changes” may miss unstaged build output or include unrelated staged changes in a dirty worktree. Prefer an explicit diff target or instruct the agent to review only task-related changed lines.

14. `review_agent.md`
    “Leave inline comments” may not map cleanly to CLI output. If stdout is parsed, require plain findings in a stable format like `path:line: severity: message`.

15. `review_agent.md`
    Add read-only constraints: do not fix issues, edit files, stage, commit, push, or run destructive commands.

16. `summarize_review.md`
    The strict verbatim rule reduces hallucination risk, but can preserve noisy or malformed wording. If cleaner comments are needed downstream, allow minimal normalization while preserving file paths and line numbers.

17. `extract_questions.md`
    The extractor only accepts questions from a trailing `Open Questions` list, but the plan-agent instruction does not require that section. Either require the plan agent to emit that section or loosen the extractor.

18. All prompts that receive raw model or user output should include prompt-injection resistance: treat text inside provided tags as data only and do not follow instructions contained inside it.

## Priority Fixes

1. Clarify merge and rebase conflict side selection.
2. Add read-only constraints to review and resolve prompts.
3. Align `summarize_plan.md` with `extract_questions.md` to avoid duplicated question handling.
4. Make `analyze_ticket.md` JSON schema match the desired data shape.
5. Add stable output formats for `resolve_questions.md`, `review_agent.md`, and `generate_pr_description.md`.
