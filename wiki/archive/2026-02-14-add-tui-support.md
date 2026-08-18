---
title: Add TUI support
date: 2026-02-14
type: implementation
status: resolved
session_id: -
services: [tui, main]
branch: -
tickets: [MNT-17]
tags: [tui, cli, textual, investigation]
related: []
---

# Add TUI support

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-07-21-rich-markuperror-and-run-attempts]]. See wiki/archive/ for the
> original.

## TL;DR

Originally scoped as an investigation ticket, MNT-17 resolved by choosing a Rich-based TUI approach instead of a full TUI library: a `print_message` service in `demetra/services/tui.py` replaces bare `print()` output. `main.py` was refactored into an interactive workflow loop with plan / build / review steps and argparse flags (`--auto`, `--project-name`), all rendered through Rich formatters and status widgets.

---

## Overview

The ticket started as "investigate available TUI frameworks and libraries; create necessary tickets". The investigation landed on using Rich (already Python-native, no heavy runtime) rather than adopting a full textual/library dependency, and folding the interactive experience directly into the CLI entrypoint.

## Step 1 — Add the `print_message` TUI service

**File:** `demetra/services/tui.py`

A small console helper that all workflow output goes through:

```python
def print_message(message: str, ...) -> None:
    # Rich console / panel rendering for styled output
```

This becomes the single output path for the CLI; bare `print()` calls across the codebase are replaced.

## Step 2 — Rework `main.py` into an interactive loop

**File:** `main.py`

The supervisor flow is restructured into a prompted, step-by-step loop covering plan → build → review. Added argparse flags so the loop can run unattended:

- `--auto` — skip interactive prompts (later extended by MNT-30 / MNT-34)
- `--project-name <name>` — target project

## Step 3 — Render output with Rich

Styled console output, formatters, and status widgets are added so long-running subagent steps are visually tracked instead of printing raw text.

## Test Results

No dedicated test suite was added in this change; verification was manual CLI runs of the interactive loop. Later tickets (MNT-21, MNT-37) added automated coverage over the same workflow path.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-17
