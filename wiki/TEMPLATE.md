---
title:              # Human-readable page title (should match the H1 below)
date: YYYY-MM-DD    # Session date — `date +%F`
type:               # debug | investigation | code-review | implementation
status:             # resolved | open | in-progress | reference
session_id:         # agent session id (OpenCode / Claude Code)
services: []        # e.g. [main, auth, cache, etc]
branch:             # feature/epic branch this relates to, or - if none
tickets: []         # e.g. [MNT-123], or []
tags: []            # free-form topic tags, e.g. [telemetry, agents]
related: []         # filenames of related wiki pages, e.g. [2026-07-09-multi-agent-plan-step.md]
---

# <Title>

## TL;DR

<2–4 sentences a teammate can read in 20 seconds: what this session was about and the
outcome / net effect. Lead with the conclusion, not the chronology.>

---

<!--
  BODY SECTIONS — keep, drop, and reorder the presets below to fit the page `type`.
  Conventions for every body:
    • Anchor claims to code: put `**File:** path/to/file.py:123` above the relevant snippet.
    • Prefer short, real code snippets and file:line refs over prose.
    • Cross-link sibling pages with [[filename-without-.md]] and add them to `related` above.
    • Document root causes and *why*, not just symptoms. Include what was ruled out.

  ── type: debug ──────────────────────────────────────────
      ## Symptom
      ## Step 1 — <title>        (each step: cause + evidence; number them)
      ## Step 2 — <title>
      ## Root cause
      ## Resolution / Fix
      ## Known follow-up (not fixed this session)

  ── type: investigation ──────────────────────────────────
      ## Net effect              (the practical takeaway / gap, stated up front)
      ## <Subsystem / area>      (one section per area explored)
      ## Open questions

  ── type: code-review ────────────────────────────────────
      ## Findings                (### numbered; each: **File:**, **Severity:**, problem, **Fix:**)
      ## Summary table           (| # | Severity | Repo | File | Description |)

  ── type: implementation ─────────────────────────────────
      ## Overview
      ## Step 1 — <title>        (before/after snippets)
      ## Step 2 — <title>
      ## Test Results
-->

## <first body section>

...

---

## Follow-ups

- <anything left open / next actions, or "None">

## References

- Related: [[<related-page-filename-without-.md>]]
- External: <Linear / Notion / URL - or omit this line>
