---
title: 'MNT-205 — Revise merged environment: context.environment resolver'
date: 2026-09-16
type: implementation
status: resolved
session_id: ses_f55832b3effeWJy0LClcVV2V83
services: [library, workflows, settings]
branch: mnt-205-revise-merged-environment
tickets: [MNT-205]
tags: [wiki, backend, feature]
related: [2026-08-10-process-environment-3-layers-encryption-uv-venv.md, 2026-08-18-categorize-settings-env-vars-by-layer.md]
---
# MNT-205 — Revise merged environment: context.environment resolver

## TL;DR

The implementation standardized methods for resolving agent models, Linear settings, and OpenRouter settings by introducing a single SessionEnvironment resolver. This resolver is exposed as the environment property on the Context object, allowing all workflow steps and helpers to read from the same place. The outcome is a more streamlined and efficient way of managing environment settings. All tests have passed, and the necessary wiki pages have been updated.

---

## Overview

The SessionEnvironment resolver was implemented in demetra/library/models.py, which looks up workflow environment keys through three layers: project environment, user-shared environment, and settings defaults. Key files and components updated include demetra/library/exceptions.py and demetra/services/agents/opencode.py. The changes aim to provide a unified way of accessing environment settings across the application.

## Build plan

## Implementation Plan
The implementation plan involves standardizing the methods for resolving agent models, Linear settings, and OpenRouter settings by introducing a single `SessionEnvironment` resolver. This resolver will be exposed as the `environment` property on the `Context` object, allowing all workflow steps and helpers to read from the same place.

### Key Technical Decisions
- Introduce a `SessionEnvironment` resolver in `demetra/library/models.py` that looks up workflow environment keys through three layers: project environment, user-shared environment, and settings defaults.
- Raise an `EnvironmentConfigError` when a key is not found in any of the layers.
- Expose the `SessionEnvironment` resolver as the `environment` property on the `Context` object.
- Delete duplicate resolvers (`…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f55832b3effeWJy0LClcVV2V83`

---

## Follow-ups

- None

> **Consistency fix (2026-09-18, Consistency Agent):** Quoted `title` containing `:` for valid YAML.

## References

- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]], [[2026-08-18-categorize-settings-env-vars-by-layer]]
- External: https://linear.app/mnt/issue/MNT-205/revise-merged-environment

> **Consistency fix (2026-09-28, Consistency Agent):** `related:` was empty and `services:` was a ~150-entry dump of filenames/wiki slugs from the wiki generator (since trimmed to subsystem tags). The `Changed files`/`Stat` sections below are a whole-tree diff, not this ticket's changeset: they correctly include the ticket's real deletions (`demetra/services/linear/config.py`, `demetra/services/llm/config.py`, both deleted in `68e53b7` and folded into the resolver) but also sweep in unrelated churn — e.g. `wiki/pages/2026-09-10-mnt-200-update-research-loop.md`, `2026-09-11-mnt-203-create-related-ticket-for-research.md` and `2026-09-14-research-plan-artifact.md` shown as deleted although all three exist on HEAD, plus the never-committed duplicate `2026-09-16-mnt-205-context-environment.md`. Do not trust per-file counts below; the ticket's substance is the `SessionEnvironment` resolver in the TL;DR/Overview.
