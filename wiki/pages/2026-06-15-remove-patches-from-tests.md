---
title: Remove patches from tests where possible
date: 2026-06-15
type: implementation
status: resolved
session_id: "-"
services: [tests, database]
branch: "-"
tickets: [MNT-106]
tags: [tests, fixtures, refactor, docker]
related: []
---

# Remove patches from tests where possible

## TL;DR

Replaced `patch` DB mocks with fixtures/factories and local service calls with real invocations (third-party calls may stay mocked). Added Docker amd64/ARM64 targets, filtered trivial "no issue" review responses, updated `.dockerignore`, added import-at-top guidance to AGENTS.md. Bumped to 1.13.0.

---

## Overview

Tests now exercise real code paths instead of mocked ones, reducing false confidence and making refactors fail loudly.

## Changes

- **DB fixtures/factories** (`tests/`): real database records replace patched repository calls — bulk of removed patches.
- **Local services**: tests call real functions instead of mocks; third-party calls may remain mocked.
- **Docker**: amd64 + ARM64 build targets, `.dockerignore` updated. Alternative to systemd deploy (MNT-119).
- **Review filtering + guidelines**: trivial "no issue" findings filtered; import-at-top guidance added to `AGENTS.md`.

## Test Results

Full suite passes after refactor; affected modules verified.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-106 — Remove patches from tests where possible (Linear)](https://linear.app/mnt/issue/MNT-106)
