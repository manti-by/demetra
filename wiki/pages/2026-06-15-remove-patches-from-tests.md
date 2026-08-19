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

Refactored the test suite to drop as many `patch` mocks as possible: DB access now uses fixtures/factories and local service calls use real function calls, while third-party service calls may stay mocked. Also added Docker support with build targets for amd64/ARM64, filtered trivial "no issue" review responses, updated `.dockerignore`, and added import-at-top guidance to AGENTS.md. Version bumped to 1.13.0.

---

## Overview

The goal was to make tests exercise real code paths rather than mocked ones, which reduces false confidence and makes refactors fail loudly.

## Step 1 — Replace DB mocks with fixtures/factories

**File:** `tests/`

Introduced fixtures and factories across the suite so tests create real database records instead of patching repository calls. This covers the bulk of the removed `patch` usages.

## Step 2 — Call local services for real

Where a test invoked a local service through a mock, it now calls the real function. Third-party service calls (external systems) may remain mocked.

## Step 3 — Docker support

Added Docker build targets for amd64 and ARM64 and updated `.dockerignore` so the image excludes irrelevant local files. Docker remains an alternative to the systemd deployment (see MNT-119).

## Step 4 — Review filtering + guidelines

- Filtered trivial "no issue" review responses so they do not surface as findings.
- Added import-at-top guidance to `AGENTS.md`.
- Version bumped to 1.13.0.

## Test Results

Full suite passes after the refactor; the fixture/factory migrations were verified by running the affected test modules.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-106 — Remove patches from tests where possible (Linear)](https://linear.app/mnt/issue/MNT-106)
