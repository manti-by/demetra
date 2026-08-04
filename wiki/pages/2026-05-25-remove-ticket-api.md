---
title: Remove ticket API
date: 2026-05-25
type: implementation
status: resolved
session_id: -
services: [api]
branch: -
tickets: [MNT-88]
tags: [api, cleanup, remove]
related: []
---

# Remove ticket API

## TL;DR

Removed the ticket-creation-from-text API added earlier (`demetra/api/tickets.py` + `demetra/services/ticket_provider.py`, the `/create-ticket` AI-extraction endpoint). The routers and tests were updated accordingly; ticket creation from raw text was dropped in favor of the Linear-native flow.

---

## Overview

The ticket API let users create tickets from raw text via AI extraction. With the Linear-native flow in place, that path was redundant and was deleted wholesale. No PR title mentions MNT-88; the removal is evidenced by orphaned bytecode for both files.

- Deleted `demetra/api/tickets.py` and `demetra/services/ticket_provider.py`
- `/create-ticket` AI-extraction endpoint removed
- Routers and tests updated
- Ticket creation from raw text dropped in favor of the Linear-native flow

## Step 1 — Delete the API and provider

Removed `demetra/api/tickets.py` (the `/create-ticket` endpoint) and `demetra/services/ticket_provider.py` (the AI text-extraction provider).

## Step 2 — Update routers and tests

Cleaned up router registration and tests to drop references to the removed endpoints.

## Evidence

The removal is confirmed by orphaned bytecode (`demetra/api/__pycache__/tickets.cpython-313.pyc` and `demetra/services/__pycache__/ticket_provider.cpython-313.pyc`) while the source files no longer exist.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-88
