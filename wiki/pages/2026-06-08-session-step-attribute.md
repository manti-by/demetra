---
title: Plan step completion attribute
date: 2026-06-08
type: implementation
status: resolved
session_id: "-"
services: [database, sessions, workflows, opencode]
branch: "-"
tickets: [MNT-83, MNT-22]
tags: [step, sessions, migration, resume, isolation, research]
related: [2026-02-21-opencode-sessions-isolation.md, 2026-07-16-fix-step-status-review-findings.md, 2026-07-21-awaiting-input-status-for-session.md, 2026-08-05-post-build-validation.md]
---

# Plan step completion attribute

## TL;DR

Added a `step` attribute to the `Session` model so an interrupted workflow can resume at the right step. Choices are `initial` (default), `plan`, `build`, `lint`, `review`, `completed`, and the field is updated after each workflow step completes — e.g., if the plan step has questions they are posted, and on the next run the workflow checks `step` instead of `build_plan` existence. The change set also restored AGENTS.md and `.opencode/agents/*.md`.

---

## Overview

Resume support: previously the workflow inferred how far a session had gotten from the presence of a `build_plan`. An explicit `step` makes the progress durable and unambiguous. PR #36 was closed unmerged; the field actually landed via PR #37 "MNT-81: Add session steps, restore AGENTS.md" (migration `e5f6a7890123_add_step_field_to_sessions.py`).

- `step` attribute on the `Session` model: `initial` (default), `plan`, `build`, `lint`, `review`, `completed`
- Alembic migration `add_step_field_to_session_model`
- Step updated after each workflow step completes
- Resume checks `step` instead of `build_plan` existence

## Step 1 — `step` attribute on the model

Added the `step` field to the `Session` model with the choices `initial`, `plan`, `build`, `lint`, `review`, `completed`, defaulting to `initial`.

## Step 2 — Migration

Added the Alembic migration named `add_step_field_to_session_model` (landed as `e5f6a7890123_add_step_field_to_sessions.py`), backfilling existing sessions to `initial`.

## Step 3 — Resume logic

The step field is updated after each workflow step completes. When the plan step has questions, they are posted as before, but on the next run the workflow now checks `step` to decide where to continue instead of checking for the existence of `build_plan`.

## Step 4 — Docs restore

AGENTS.md and `.opencode/agents/*.md` were restored in the same change set.

## Test Results

Tests were added for the step field and resume behavior.

---

## Source — [[2026-02-21-opencode-sessions-isolation]]

Originally researched in [[2026-02-21-opencode-sessions-isolation]] on 2026-02-21
(MNT-22): OpenCode's `run` accepts a custom `--session` / session id, giving
deterministic control over which session each workflow step uses. Demetra generates
one id per workflow run, passes it to every `opencode run` invocation (plan, build,
review) and stores it on the `sessions` row — the durable link between the workflow
and its OpenCode sessions. This is what unblocked parallel workflows and later
enabled per-session state: session history, compaction, and log isolation (MNT-54).

## Follow-ups

- None.

> **Update (2026-08-19):** The current `StepType` enum in `demetra/library/models.py` has
> 11 values: `initial`, `plan`, `build`, `validate`, `review`, `lint`, `test`, `push`,
> `completed`, `failed`, `awaiting_input`. `validate` was added for the post-build
> validate-agent (see [[2026-08-05-post-build-validation]]); `awaiting_input` was added
> for the Awaiting Input state (see [[2026-07-21-awaiting-input-status-for-session]]).
> The step vocabulary documented in this page is the historical snapshot from the MNT-83 era.

## References

- Related: [[2026-07-16-fix-step-status-review-findings]] — later review of the same `sessions.step` subsystem
- External: https://linear.app/mnt/issue/MNT-83
