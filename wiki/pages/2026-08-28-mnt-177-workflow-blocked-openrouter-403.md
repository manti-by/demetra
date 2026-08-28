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
related: [2026-08-24-guard-empty-plan-output.md, 2026-08-18-migrate-llm-groq-to-openrouter.md]
---

# MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation

## TL;DR

The MNT-177 (`Research loop`) workflow was retried 6 times on amon-ra (2026-08-28) and never completed. Three distinct failure signatures were isolated: the MNT-162 empty-summarizer path (`Plan is empty, exiting the workflow.`, once), the plan agent being cut off by an auto-rejected `read (.env.docker.example)` tool call (no `## Implementation Plan` header, twice), and — the dominant blocker (3 of 6 runs) — an **OpenRouter HTTP 403** from `extract_plan` because the user-shared `OPENROUTER_MODEL=meta/muse-spark-1.2` requires an uncompleted **18+ age attestation**. Verified both models directly against the OpenRouter key: `meta-llama/llama-3.3-70b-instruct` works (200 OK), `meta/muse-spark-1.2` 403s with `age_18plus`. The MNT-162 hardening (treat empty `extract_plan` as `PlanError`) is valid but does not fix these blockers.

---

## Symptom

Demetra posted `## Error\nPlan step failed: ...` comments on MNT-177 and kept moving the ticket back to Awaiting Input / Todo. Worker log (`/mnt/data/www/demetra/log/worker.log`) showed six `Retrieved task: MNT-177` runs between 07:27 and 10:00, all failing in the plan step.

## Step 1 — Categorize the six runs into three failure signatures

From worker.log (all 2026-08-28):

| Time | Error | Root cause |
|------|-------|-----------|
| 07:35 | `Plan is empty, exiting the workflow.` | The MNT-162 finding: raw plan was valid (`## Implementation Plan` + `Ready to proceed to build.` present), but `extract_plan` returned empty content → `plan.py:101` returned `None`. Fired **once**. |
| 09:33, 09:51 | `Plan agent output is missing the implementation plan section` | Plan agent run truncated mid-investigation. Last tool call before exit: `! permission requested: read (.env.docker.example); auto-rejecting` → `✗ Read .env.docker.example failed` → `Error: The user rejected permission to use this specific tool call.` Output ended with commentary only, no plan header. Not a summarizer issue. |
| 09:40, 09:44, 10:00 | `Failed to summarize the build plan` | OpenRouter **403 PermissionDeniedError**: `extract_plan` → `build_llm` resolved `OPENROUTER_MODEL=meta/muse-spark-1.2` from the user-shared env and OpenRouter rejected it with `This model requires you to complete the following before use: 18+ age confirmation.` (metadata `age_18plus`). Dominant blocker (**3 of 6**). |

## Step 2 — Trace the 403 to the resolved model

`extract_plan` (`demetra/services/llm/openrouter.py:150-191`) → `build_llm` (`demetra/services/llm/factory.py`) → `get_openrouter_config(user_id=...)` (`demetra/services/llm/config.py:24-25`): the **user-shared env override wins** over the container default. The `project_environment` table (user `470ec65e-df79-41d9-bb8a-22a7bfec0688`, `scope=user`) holds `OPENROUTER_MODEL=meta/muse-spark-1.2`, while `.env.docker` only sets `google/gemini-3.7-flash` for non-overridden users. So every `extract_plan`/`summarize_*` call used `meta/muse-spark-1.2` and 403'd.

`meta/muse-spark-1.2` is exactly the model the MNT-162 comment by the requester suggested trying — so the suggestion was applied and became the very cause of the recurring failure.

## Step 3 — Verify both models against the OpenRouter key

Tested directly against `https://openrouter.ai/api/v1/chat/completions` with the production `OPENROUTER_API_KEY`:

- `meta-llama/llama-3.3-70b-instruct` → **200 OK**, no attestation required.
- `meta/muse-spark-1.2` → **403** `{code: 403, metadata: {missing_attestation_types: ["age_18plus"]}}` — matches production logs byte-for-byte.

## Root cause

MNT-177's workflow could not complete because of two independent production issues:

1. **OpenRouter model attestation (dominant):** user-shared `OPENROUTER_MODEL=meta/muse-spark-1.2` requires 18+ age confirmation that the OpenRouter account (`user_3BDI24M6TiVlok3buh8FEZD18Iz`) has not completed → every summarize call 403s → `PlanError` → Awaiting Input.
2. **Plan agent truncation:** an auto-rejected `read (.env.docker.example)` tool call ends the plan-agent run with output lacking the `## Implementation Plan` header → `PlanError`. This is the same permission-rejection class already documented in [[2026-08-24-guard-empty-plan-output]]; the guard now surfaces it as an error comment instead of a hallucinated plan, but the underlying opencode behavior is still not fixed.

The MNT-162 hardening (empty `extract_plan` → `PlanError`) only addresses signature 1 (the single 07:35 run). It would not let the workflow complete — the 403 path already raises `PlanError`.

## Resolution / Fix

- Change the user-shared `OPENROUTER_MODEL` from `meta/muse-spark-1.2` to `meta-llama/llama-3.3-70b-instruct` (verified working), **or** complete the 18+ attestation at https://openrouter.ai/settings/preferences.
- Separately investigate the opencode permission auto-rejection (`read .env.docker.example`) that truncates plan-agent runs.

## Known follow-up (not fixed this session)

- The plan-agent truncation on permission auto-rejection remains open (see the Follow-ups section of [[2026-08-24-guard-empty-plan-output]]).
- Whether `extract_plan`'s empty-result path (signature 1) should raise `PlanError` instead of silently returning `None` at `plan.py:101` is still a valid hardening, independent of these blockers.

## References

- Related: [[2026-08-24-guard-empty-plan-output]], [[2026-08-18-migrate-llm-groq-to-openrouter]]
- External: worker.log `/mnt/data/www/demetra/log/worker.log` (MNT-177 runs 07:27–10:00 on 2026-08-28), `project_environment` table (user env `OPENROUTER_MODEL`), https://openrouter.ai/settings/preferences