# Prompts Audit Report

Generated: 2026-06-29 by qwen3.7-max

## Summary

9 prompts reviewed. 2 already compacted (`extract_questions.md`, `summarize_review.md`). 7 have issues ranging from critical (ambiguous git terminology) to minor (redundant instructions).

---

## Critical Issues

### merge_agent.md — Contradictory git terminology
Line 12 says "prefer the version from the branch being merged in (theirs/base branch)". In a merge, "theirs" = incoming branch, "base" = target branch. These are opposites. Could cause the agent to resolve conflicts incorrectly.

**Fix**: Pick one — likely "theirs" (incoming branch) based on context.

### rebase_agent.md — Ambiguous terminology
Line 12 says "prefer the version from the branch being rebased onto (theirs/base branch)". Technically correct for rebase (theirs = upstream), but "base branch" adds ambiguity.

**Fix**: Drop "base branch", keep only "theirs" or clarify explicitly.

---

## High Issues

### generate_pr_description.md — Too vague, no guardrails
- No output format spec, no length constraints, no examples
- No hallucination guardrails (agent could invent details not in the plan)
- No mention of referencing Linear ticket ID
- "Keep it brief but informative" is unmeasurable

**Fix**: Add structured format, length limits, extraction-only constraint, ticket ID reference.

### summarize_plan.md — No extraction guardrails, overlaps with extract_questions.md
- No "extraction only" constraint unlike other prompts — agent can hallucinate plan details
- Line 21 says to include questions, but `extract_questions.md` handles questions separately — potential duplication
- "Focus on the actual implementation steps/plan" is circular
- "clean markdown format" has no structure

**Fix**: Add extraction-only constraint, remove question handling (defer to `extract_questions.md`), specify output structure.

### resolve_questions.md — No output format, no fallback
- Doesn't specify how answers should be structured
- No instruction for unanswerable questions
- No warning against making assumptions without evidence

**Fix**: Add output format (e.g., JSON or numbered answers with citations), add fallback for unanswerable questions, add guardrails against speculation.

---

## Medium Issues

### analyze_ticket.md — Redundant instructions, grammar error, contradictions
- Lines 27-29 repeat formatting guidance ("list of items with dashes", "clear list of requirements", "bullet points")
- Grammar error in JSON example: `"A project name this ticket is belonging"` → should be `"belongs to"`
- Line 33 says "no markdown" but section headers above use `**bold**`
- Line 32 hardcodes project names `ODIN, Demetra, Coruscant` — consider making configurable

**Fix**: Deduplicate formatting rules, fix grammar, resolve markdown contradiction, consider externalizing project list.

### review_agent.md — Vague instruction, slightly verbose
- "Check git staged changes" doesn't specify how (git diff? git status?)
- IMPORTANT section could be slightly compacted while keeping guardrails

**Fix**: Specify the exact command or approach, compact the IMPORTANT section.

---

## Low / No Issues

| Prompt | Status |
|---|---|
| `extract_questions.md` | Compacted — no issues |
| `summarize_review.md` | Compacted — no issues |

---

## Priority Order

1. **merge_agent.md** — fix contradictory terminology (could cause wrong conflict resolution)
2. **rebase_agent.md** — clarify terminology
3. **generate_pr_description.md** — add format and guardrails
4. **summarize_plan.md** — add extraction guardrails, resolve overlap
5. **resolve_questions.md** — add output format and fallback
6. **analyze_ticket.md** — deduplicate, fix grammar
7. **review_agent.md** — minor tightening
