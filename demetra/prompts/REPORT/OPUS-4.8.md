# Prompts Review Report

**Date:** 2026-06-29
**Reviewer:** Claude Opus 4.8
**Scope:** All prompt files in `demetra/prompts/` plus the loading path (`demetra/services/prompt.py` and call sites in `demetra/services/groq.py`, `merge.py`, `rebase.py`, `workflows/resolve.py`).

---

## How prompts are loaded

`get_prompt(name, **kwargs)` reads `demetra/prompts/{name}.md`. If kwargs are passed, it applies Python `str.format(**kwargs)`; otherwise it returns the raw file. There are **two distinct delivery paths**, and they imply different brace rules:

- **`str.format` prompts** — `merge_agent`, `rebase_agent`, `resolve_questions`. Called via `get_prompt(..., **kwargs)`, use single `{placeholder}`, fed as the task to opencode/cursor agents.
- **LangChain `ChatPromptTemplate` system prompts** — `analyze_ticket`, `summarize_plan`, `extract_questions`, `summarize_review`, `generate_pr_description`. Called via `get_prompt(name=...)` with no kwargs, then handed to `ChatPromptTemplate` (f-string mode), so any **literal** brace must be doubled (`{{` / `}}`).

---

## 🔴 Likely bugs / correctness

### 1. `rebase_agent.md` — "theirs" is mislabeled (wrong conflict side)
Line 12: *"prefer the version from the branch being rebased onto (theirs/base branch)."*

During `git rebase`, ours/theirs are **swapped** relative to a merge: the branch you rebase **onto** is `ours` (HEAD), and your replayed commits are `theirs`. So "branch being rebased onto" = `--ours`, **not** `--theirs`. The current wording is self-contradictory and will steer the agent to the wrong side if it uses `git checkout --theirs`.

**Fix:** Drop the `theirs` alias or correct it to `ours/base branch`. Confirm intended resolution side before editing.

### 2. `summarize_plan.md` — task/plan content injected twice
The system prompt embeds `{task_description}` and `{plan_output}` placeholders (lines 23–31). But `extract_plan` in `groq.py:110` **also** passes those same values in the human message. Because the system prompt is templated by LangChain's f-string `ChatPromptTemplate`, both get filled, so the model receives the full task description and plan output **twice**.

**Fix:** Remove the placeholders from the system prompt; the content belongs only in the human turn.

### 3. `analyze_ticket.md` — schema keys don't match the code fallback
The prompt's JSON contract uses `technical_requirements` (line 17), but the fallback dict in `groq.py:95-96` returns `tech_requirements` / `acceptance_criteria`. The fallback shape doesn't match the success-path shape the prompt promises — downstream consumers will see different keys depending on whether the LLM succeeded.

**Fix:** Align the fallback dict keys with the prompt schema (`technical_requirements`).

---

## 🟡 Improvements

### 4. `analyze_ticket.md` — list-vs-string contradiction
Line 27 instructs `technical_requirements` & `acceptance_criteria` to be "a list of items with dashes," but the JSON schema types them as single strings.

**Fix:** State it explicitly, e.g. "a single string containing dash-prefixed lines, one item per line."

### 5. `generate_pr_description.md` — thin, no anti-fabrication guard
Unlike the extraction prompts, this one has no instruction against inventing changes not present in the plan/diff.

**Fix:** Add a line such as: *"Only describe changes actually present in the task and plan; do not invent features or files."*

### 6. `merge_agent.md` — incomplete stop-instruction parity with rebase
`rebase_agent.md` forbids `git rebase --continue`; `merge_agent.md` only says "Do NOT commit."

**Fix:** For symmetry and safety, also forbid `git merge --continue` / `--abort` and pushing.

---

## 🟢 Cross-cutting / consistency

### 7. Two undocumented brace conventions (foot-gun)
See the loading section above. `analyze_ticket.md` correctly uses `{{ }}`. Anyone adding a literal `{` to a LangChain-fed prompt without doubling it will get silent variable injection or a `KeyError`.

**Fix:** Add a short comment in `services/prompt.py` documenting which prompts go through which path.

### 8. Solid, no changes needed
- `review_agent.md` — strong silent-success guardrails, consistent with the `summarize_review` ignore-list.
- `resolve_questions.md` — clean.
- `extract_questions.md` and `summarize_review.md` — recently restored the "when in doubt, do NOT output" tie-breaker guardrail.

---

## Summary table

| # | File | Severity | Issue |
|---|------|----------|-------|
| 1 | `rebase_agent.md` | 🔴 | "theirs" mislabeled — wrong conflict side during rebase |
| 2 | `summarize_plan.md` | 🔴 | Task/plan content injected twice (system + human) |
| 3 | `analyze_ticket.md` | 🔴 | Fallback dict keys don't match prompt JSON schema |
| 4 | `analyze_ticket.md` | 🟡 | List-vs-string contradiction in field guidance |
| 5 | `generate_pr_description.md` | 🟡 | No anti-fabrication guard |
| 6 | `merge_agent.md` | 🟡 | Incomplete stop-instruction parity with rebase |
| 7 | `services/prompt.py` | 🟢 | Two undocumented brace conventions |
| 8 | `review_agent.md`, `resolve_questions.md`, `extract_questions.md`, `summarize_review.md` | 🟢 | No changes needed |
