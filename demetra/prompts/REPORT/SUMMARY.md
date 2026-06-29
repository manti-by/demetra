# Prompts Review — Consolidated Report

Synthesis of three independent reviews of the prompts in `demetra/prompts/`:
`PROMPTS_REPORT_GPT-5.5.md`, `PROMPTS_REPORT_OPUS-4.8.md`, `PROMPTS_REPORT_QWEN-3.7.md`.

Agreement is marked per finding (✓✓✓ = all three models). Discrepancies — where the
models disagree on facts or verdicts — are flagged with ⚠️ and collected at the end.

---

## 🔴 `merge_agent.md` & `rebase_agent.md` — Ambiguous git conflict terminology

**Top-priority issue flagged by all three models** — but they disagree on the actual git semantics.

- **GPT-5.5**: For *rebase*, ours/theirs are inverted vs. merge; `theirs/base branch` may pick the
  wrong side. Clarify the desired side explicitly without relying on ours/theirs.
- **Opus-4.8**: For *rebase*, "branch being rebased onto" = `--ours`, **not** `--theirs` — the label
  is self-contradictory and wrong. (Opus's git mechanics are correct: during rebase the branch you
  rebase onto is `ours`/HEAD, replayed commits are `theirs`.)
- **Qwen-3.7**: For *rebase*, claims the wording is "technically correct (theirs = upstream)" —
  ⚠️ **directly contradicts Opus**. For *merge*, says intended side is likely "theirs" (incoming).

**Consensus action:** drop or correct the `theirs/base branch` alias; state the desired side
explicitly. **Verify the rebase mechanics manually before fixing** (Opus appears correct).

- **GPT-5.5 (only):** add conflict-resolution safeguards — inspect each conflicted file before editing,
  remove all conflict markers, avoid unrelated files, stage only resolved files, verify the result.

## 🔴 `rebase_agent.md` / `merge_agent.md` — Stop-instruction parity

- **GPT-5.5 (only):** keep `Do NOT run git rebase --continue` prominent — the service runs
  `--continue` after the agent stages files.
- **Opus (only):** `merge_agent.md` lacks parity — it only says "Do NOT commit"; should also forbid
  `git merge --continue` / `--abort` and pushing.

## 🔴 `summarize_plan.md` — Duplicate / overlapping content & question handling

**All three** flag the overlap with `extract_questions.md`:
- ✓✓✓ Questions are extracted separately; including them here duplicates unresolved questions →
  defer question handling to `extract_questions.md`.
- **Opus (only) — concrete bug:** `{task_description}` and `{plan_output}` placeholders are injected
  **twice** (LangChain f-string system prompt + the human message in `groq.py:110`). Fix: remove the
  placeholders from the system prompt; content belongs only in the human turn.
- **GPT-5.5 & Qwen:** add an "extraction-only" constraint — do not invent files, steps, requirements,
  or technical decisions not present in the plan output.

## 🔴 `analyze_ticket.md` — Schema / field inconsistencies

- **Opus (only) — concrete bug:** fallback dict in `groq.py:95-96` returns
  `tech_requirements` / `acceptance_criteria`, but the prompt schema uses `technical_requirements`.
  Keys diverge depending on whether the LLM succeeded. Fix: align fallback keys with the schema.
- ✓✓✓ **List-vs-string contradiction:** `technical_requirements` & `acceptance_criteria` are typed as
  strings but instructions ask for dashed lists. Fix: use JSON arrays, or explicitly require
  newline-delimited dash-prefixed strings.
- **GPT-5.5 & Qwen:** hardcoded project names (`ODIN`, `Demetra`, `Coruscant`).
  ⚠️ GPT-5.5 wants a **deterministic fallback** when no project matches; Qwen wants the list
  **externalized/configurable** (related, not conflicting).
- **GPT-5.5 (only):** "make reasonable assumptions" can fabricate requirements — prefer null/empty or
  mark inferred information.
- **Qwen (only):** grammar error `"is belonging"` → `"belongs to"`; markdown contradiction (says
  "no markdown" but headers use `**bold**`); redundant formatting instructions (lines 27–29).

## 🟡 `generate_pr_description.md` — Too vague, no guardrails

(GPT-5.5 & Qwen high priority; Opus 🟡. *Note: not in the current change set — may be pre-existing.*)
- ✓✓✓ Add an anti-fabrication / extraction-only constraint.
- ✓✓✓ Add a structured output template (e.g. Summary / Changes / Testing).
- **GPT-5.5:** define behavior when testing info is unavailable.
- **Qwen:** add length limits; reference the Linear ticket ID.

## 🟡 `resolve_questions.md` — Output format & safeguards

⚠️ **Verdict discrepancy:** Opus marks it **clean / no changes (🟢)**; GPT-5.5 & Qwen want changes.
- **GPT-5.5 & Qwen:** add a strict answer format (numbered Q/A with evidence/citations:
  `path:line, symbol`).
- **GPT-5.5:** make it explicitly read-only (no edits/staging/commits/destructive commands).
- **Qwen:** add a fallback for unanswerable questions; add a guard against speculation.

## 🟡 `review_agent.md` — "Check git staged changes" is vague

⚠️ **Verdict discrepancy:** Opus marks it **solid / no changes (🟢)**; GPT-5.5 & Qwen want changes.
- **GPT-5.5 & Qwen:** "check git staged changes" is underspecified — may miss unstaged output or
  include unrelated staged changes; specify the exact diff target/command.
- **GPT-5.5:** define a stable findings format (`path:line: severity: message`) since "inline comments"
  may not map to CLI stdout; add explicit read-only constraints.
- **Qwen:** compact the IMPORTANT section while keeping guardrails.

## 🟡 `extract_questions.md`

⚠️ **Verdict discrepancy:** Opus & Qwen mark it **compacted / no issues (🟢)**; GPT-5.5 raises a
structural concern — the extractor only reads a trailing `Open Questions` list, but the plan agent
isn't required to emit that section. Fix: require the section upstream, or loosen the extractor.

## 🟢 `summarize_review.md` — Largely fine

- **Opus & Qwen:** no issues / compacted.
- **GPT-5.5 (only):** strict verbatim rule preserves noisy/malformed wording; consider allowing
  minimal normalization while preserving file paths and line numbers.

## 🟢 Cross-cutting (single-model observations)

- **Opus (only):** two undocumented brace conventions in `services/prompt.py` — `str.format` prompts
  use `{x}`; LangChain prompts need `{{ }}`. A foot-gun; document which path each prompt uses.
- **GPT-5.5 (only):** add prompt-injection resistance to all prompts ingesting raw model/user output —
  treat tagged text as data, not instructions.

---

## Key discrepancies to resolve

| Topic | Disagreement |
|---|---|
| **Rebase conflict side** | GPT-5.5 + Opus: label is **wrong**. Qwen: label is **technically correct**. (Opus's git mechanics appear right — verify manually.) |
| **`resolve_questions.md`** | Opus: clean. GPT-5.5 + Qwen: needs output format + guardrails. |
| **`review_agent.md`** | Opus: no changes. GPT-5.5 + Qwen: vague, needs format/command spec. |
| **`extract_questions.md`** | Opus + Qwen: fine. GPT-5.5: structural mismatch with plan agent. |
| **Hardcoded project names** | GPT-5.5: add deterministic fallback. Qwen: externalize the list. |

## Findings only one model caught (likely real)

- **Opus:** `summarize_plan` double-injection bug; `analyze_ticket` fallback-key mismatch in
  `groq.py`; brace-convention documentation. *(Most code-grounded — Opus inspected the loading path
  and call sites.)*
- **GPT-5.5:** prompt-injection hardening; rationale for the `--continue` warning.
- **Qwen:** grammar error and markdown self-contradiction in `analyze_ticket.md`.

## Strongest consensus (act first)

1. Fix the merge/rebase conflict-side terminology (verify rebase mechanics first).
2. Resolve the `summarize_plan` ↔ `extract_questions` question-handling overlap.
3. Address Opus's two concrete, code-verified bugs (double injection; fallback-key mismatch).
