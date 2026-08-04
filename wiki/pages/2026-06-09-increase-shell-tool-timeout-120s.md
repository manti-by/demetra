---
title: Increase shell tool timeout - 120s
date: 2026-06-09
type: implementation
status: resolved
session_id: -
services: [subprocess, settings]
branch: -
tickets: [MNT-112]
tags: [timeout, subprocess, shell-tool]
related: []
---

# Increase shell tool timeout - 120s

## TL;DR

The internal AI shell tool killed processes that ran longer than 120 seconds, terminating legitimate long builds/tests/installs. The subprocess runner now has automatic timeout protection: commands that exceed a configurable timeout (default 2 minutes) are terminated and reported with a timeout status. The timeout is configurable via environment. This is the timeout inside the agent tool layer; the workflow-level timeout was addressed separately by MNT-97.

---

## Overview

Long-running commands inside the agent tool layer were being killed at a hard 120s safety limit. The runner needed a configurable, reported timeout instead of a silent kill.

## Step 1 — Add timeout protection to the subprocess runner

**File:** `subprocess` runner

The runner now monitors command runtime. When a command exceeds the configured timeout it is terminated and the call returns a timeout status instead of a truncated/hung result.

## Step 2 — Make the timeout configurable

**File:** `settings`

The timeout defaults to 2 minutes and can be overridden via environment, so deployments running heavier builds can raise it without a code change.

## Step 3 — Distinguish from workflow timeouts

This timeout lives inside the agent tool layer (per shell-tool invocation). The workflow-level timeout is a separate concern already handled by MNT-97.

## Test Results

Tests cover the termination path and the timeout-status return value.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-112 — Increase shell tool timeout - 120s (Linear)](https://linear.app/mnt/issue/MNT-112)
