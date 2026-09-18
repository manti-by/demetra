---
title: MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation
date: 2026-08-28
type: debug
status: resolved
session_id: "-"
services: [workflows, llm, openrouter, opencode, linear]
branch: "-"
tickets: [MNT-162, MNT-177]
tags: [openrouter, model, age-attestation, 403, plan-agent, extract-plan, permission, minimax, muse-spark]
related:
- 2026-08-24-guard-empty-plan-output.md
- 2026-08-18-migrate-llm-groq-to-openrouter.md
---

# MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation

## TL;DR

MNT-177 retried 6× on 2026-08-28 and never left the plan step. Dominant cause (3/6 runs) was OpenRouter 403 on `meta/muse-spark-1.2` requiring 18+ attestation; 2 runs truncated by auto-rejected `read (.env.docker.example)` permission (no `## Implementation Plan` header); 1 run hit the MNT-162 empty-`extract_plan` path. Fix is switching `OPENROUTER_MODEL` to `meta-llama/llama-3.3-70b-instruct` or completing attestation.

---

## Symptom

Worker log `/mnt/data/www/demetra/log/worker.log` shows six `Retrieved task: MNT-177` runs 07:27–10:00, all failing in plan with `## Error / Plan step failed` comments and ticket cycling back to Awaiting Input/Todo.

## Three failure signatures

| Time | Error | Root cause |
|------|-------|------------|
| 07:35 | `Plan is empty, exiting the workflow.` | Raw plan valid (`## Implementation Plan` + `Ready to proceed` present) but `extract_plan` returned empty → `plan.py:101` returned `None`. Once. |
| 09:33, 09:51 | `Plan agent output is missing the implementation plan section` | Plan agent truncated after `! permission requested: read (.env.docker.example); auto-rejecting` → `Error: The user rejected permission…` — output lacked plan header, not a summarizer issue. |
| 09:40, 09:44, 10:00 | `Failed to summarize the build plan` | OpenRouter 403 `PermissionDeniedError` from `extract_plan` using `OPENROUTER_MODEL=meta/muse-spark-1.2` (metadata `age_18plus`). Dominant (3/6). |

## 403 trace

`extract_plan` (`demetra/services/llm/openrouter.py:150-191`) → `build_llm` (`demetra/services/llm/factory.py`) → `get_openrouter_config(user_id=...)` (`demetra/services/llm/config.py:24-25`): user-shared env wins over container default. `project_environment` (user `470ec65e-df79-41d9-bb8a-22a7bfec0688`, `scope=user`) held `OPENROUTER_MODEL=meta/muse-spark-1.2`; `.env.docker` default `google/gemini-3.7-flash` was overridden. Model was suggested in the MNT-162 comment — the suggestion itself caused the failure.

## Verification

Direct `https://openrouter.ai/api/v1/chat/completions` with prod `OPENROUTER_API_KEY`:

- `meta-llama/llama-3.3-70b-instruct` → 200 OK
- `meta/muse-spark-1.2` → 403 `{code:403, metadata:{missing_attestation_types:["age_18plus"]}}` — matches prod logs

## Root cause

1. **Model attestation:** `meta/muse-spark-1.2` requires 18+ attestation not completed on account `user_3BDI24M6TiVlok3buh8FEZD18Iz` → every summarize call 403s → `PlanError`.
2. **Plan agent truncation:** auto-rejected `read .env.docker.example` ends run without `## Implementation Plan` header → `PlanError`. Same class as [[2026-08-24-guard-empty-plan-output]]; guard now surfaces it but opencode behavior unfixed.

MNT-162 hardening (empty `extract_plan` → `PlanError`) covers only the single 07:35 run; 403 path already raises `PlanError`.

## Resolution

- Change user-shared `OPENROUTER_MODEL` to `meta-llama/llama-3.3-70b-instruct`, or complete 18+ attestation at https://openrouter.ai/settings/preferences.
- Separately fix opencode permission auto-rejection for `read .env.docker.example`.

## Follow-ups

- Plan-agent truncation on permission auto-rejection remains open (see [[2026-08-24-guard-empty-plan-output]]).
- Whether empty `extract_plan` should raise `PlanError` at `plan.py:101` remains valid hardening independent of these blockers.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-24-guard-empty-plan-output]], [[2026-08-18-migrate-llm-groq-to-openrouter]]
- External: worker.log `/mnt/data/www/demetra/log/worker.log` (MNT-177 07:27–10:00 2026-08-28), `project_environment` table, https://openrouter.ai/settings/preferences
