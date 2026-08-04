---
title: Add Plan loop to resolve questions
date: 2026-06-02
type: implementation
status: resolved
session_id: -
services: [workflows, opencode, main]
branch: -
tickets: [MNT-79]
tags: [plan-loop, resolve-agent, questions, auto]
related: []
---

# Add Plan loop to resolve questions

## TL;DR

Automated the plan question round-trip: a separate resolve agent answers the plan agent's questions in `auto` mode instead of posting them to Linear. Added `.opencode/agents/resolve-agent.md` (checks the repo and answers the plan agent's questions) and a `--plan-loop` argument to `main.py` that loops plan and resolve agents, with max attempts read from settings (default 30). The resolve agent always gets a fresh session id.

---

## Overview

Previously, questions from the plan step were posted to Linear for a human. With `--plan-loop`, they are instead sent to a resolve agent that inspects the repo and answers them, letting the whole plan phase complete autonomously. Works alongside `--auto`.

- `.opencode/agents/resolve-agent.md` — checks the repo, answers the plan agent's questions
- `--plan-loop` argument to `main.py` — loops plan and resolve agents
- Questions sent to the resolve agent instead of Linear
- Max attempts read from settings (default 30)

## Step 1 — Resolve agent

**File:** `.opencode/agents/resolve-agent.md`

Added the resolve agent definition. It receives the original task plus the plan agent's questions, checks the repository, and returns answers.

## Step 2 — `--plan-loop` argument

**File:** `main.py`

Added a `--plan-loop` CLI argument that runs alongside `--auto`. When set, plan questions are routed to the resolve agent instead of being posted to Linear.

## Step 3 — Loop and limits

The plan workflow loops between the plan and resolve agents, re-running the plan agent each iteration to revalidate the answers. Max attempts are read from settings, defaulting to 30.

## Step 4 — Session handling

The resolve agent always runs with a NEW session id, keeping its activity distinct from the plan step.

## Test Results

Tests were added for the plan-loop workflow. Minor version bumped and README updated.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-79
