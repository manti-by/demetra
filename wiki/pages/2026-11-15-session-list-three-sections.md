---
title: 'Session list split into active, completed and backlog sections'
date: '2026-11-15'
type: implementation
status: resolved
session_id: ses_e1fda1d84ffe8DTiZYxz45gjjo
services: [SessionList, App.css, StyleGuide, SessionList.test]
branch: master
tickets: []
tags: [frontend, sessions, ui]
related: [2026-11-12-ch-12-session-list-order.md, 2026-11-04-chat-session-list-and-rerun.md]
---

# Session list split into active, completed and backlog sections

## TL;DR

The sidebar session list went from two blocks (active above, everything else as
"Backlog") to three explicitly labelled sections: **Active** (in progress,
including `awaiting_input`, updated within the last two weeks or running right
now), **Completed** (`completed` / `researched`, any age) and **Backlog**
(`failed`, plus in-progress sessions untouched for 14+ days). Active always
renders — with `No active sessions` when empty — while Completed and Backlog
only appear when non-empty. Section headers draw the horizontal rules between
blocks.

## Overview

Before this change `SessionList` classified every session with one predicate:
terminal steps (`completed`/`failed`/`researched`) **or** a `created_at` older
than 14 days fell into a single "Backlog" block under one header. Finished work
therefore ended up next to stale in-progress work, and a fresh `failed` run
carried no signal at all beyond its badge.

**File:** `react/src/components/SessionList.tsx:8-15`

The grouping now uses last activity and three buckets:

```ts
const COMPLETED_STEPS = new Set(["completed", "researched"]);
const isCompletedStep = (step: string | null | undefined): boolean =>
  COMPLETED_STEPS.has(step ?? "");

type SessionSection = "active" | "completed" | "backlog";
```

## Step 1 — One shared `sectionOf` classifier

**File:** `react/src/components/SessionList.tsx:39-56`

```ts
const isStaleSession = (session: Session, now: number): boolean => {
  const updatedAt = new Date(session.updated_at).getTime();
  if (Number.isNaN(updatedAt)) return false;
  return now - updatedAt >= ACTIVE_WINDOW_MS;
};

const sectionOf = (
  session: Session,
  now: number,
  liveTaskIds: Set<string>,
): SessionSection => {
  if (isCompletedStep(session.step)) return "completed";
  if (session.step === "failed") return "backlog";
  if (!liveTaskIds.has(session.task_id) && isStaleSession(session, now)) {
    return "backlog";
  }
  return "active";
};
```

Why each branch sits where it does:

- **Completed wins first** — `researched` sessions are closed work even when
  they are 30 days old; the age window must not pull them back.
- **`failed` is backlog immediately** — a failed run is finished, but it is not
  a success, so it ages out of the list rather than sitting among completed
  work. It stays out of Active no matter how recent it is (the previous
  implementation already did this).
- **Staleness is measured from `updated_at`, not `created_at`** — a session
  created three weeks ago but touched yesterday is still in progress.
- **A live run is never stale** — `liveTaskIds` (polled every 5 s from
  `GET /api/v1/sessions/live`) overrides the age check, so a long-running job
  cannot disappear into the backlog mid-run.

## Step 2 — Grouping and default selection

**File:** `react/src/components/SessionList.tsx:214-230`

The memo now depends on `liveTaskIds` as well as the filtered sessions, because
the live set changes which bucket a session lands in:

```ts
for (const session of filteredSessions) {
  const section = sectionOf(session, now, liveTaskIds);
  if (section === "completed") completed.push(session);
  else if (section === "backlog") backlog.push(session);
  else active.push(session);
}
```

Ordering within each section is untouched — the API order (`created_at` DESC)
is preserved, as before.

The auto-select effect reuses the same classifier so the session opened on first
load is the first **active** one, falling back to the first Linear session when
nothing is in progress (it previously looked for any non-terminal step, which
would have landed on a recent `failed` session).

## Step 3 — Rendering the three sections

**File:** `react/src/components/SessionList.tsx:242-260`

A `renderSection` helper emits the header (title + count) and either the items
or the optional empty message:

```tsx
{renderSection("Active", activeSessions, "No active sessions")}
{completedSessions.length > 0 && renderSection("Completed", completedSessions)}
{backlogSessions.length > 0 && renderSection("Backlog", backlogSessions)}
```

- Active is unconditional: its header and either sessions or
  `No active sessions` always render, so the list never looks broken when
  everything has finished.
- Completed and Backlog are conditional, matching the old Backlog behaviour.
- The pre-existing `No sessions found` / `No matching sessions` states still
  short-circuit before any section renders.

## Step 4 — Styling the dividers and empty state

**File:** `react/src/App.css:1146-1178`

`.session-section-header` keeps its `border-top` as the horizontal rule between
blocks, but the first header now sits directly under the search box, so
`:first-child` drops its rule and top margin:

```css
.session-section-header:first-child {
  margin-top: 0;
  padding-top: 0.25rem;
  border-top: none;
}

.session-section-empty {
  padding: 0.75rem 0.625rem 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-tertiary);
}
```

## Step 5 — Style guide and tests

**File:** `react/src/pages/StyleGuide.tsx:306-370`

The Sessions demo was reorganised into the same three labelled blocks and the
description now states the classification rules instead of the old two-block
wording.

**File:** `react/src/components/SessionList.test.tsx` — the
`active, completed and backlog blocks` describe block was rewritten around the
new model:

- grouping/order/count assertions for all three sections in one list
- Completed and Backlog headers omitted when empty
- `No active sessions` rendered when only finished work exists
- a recent `failed` session lands in Backlog, not Active
- a 30-day-old session stays Active while `getLiveSessionIds` reports it live
- search filtering removes a section header once all of its sessions are hidden

## Test Results

- `npx vitest run` — 14 files, 181 tests passed
- `npx tsc --noEmit` — clean

## Follow-ups

- The 14-day window lives in `ACTIVE_WINDOW_MS` and is not configurable from
  `demetra/settings.py`; revisit if product wants another cutoff.
- Sessions with an unparseable `updated_at` are treated as not stale (they stay
  Active). The API always sends an ISO timestamp, so this is defensive only.

## References

- Related: [[2026-11-12-ch-12-session-list-order]]
- Related: [[2026-11-04-chat-session-list-and-rerun]]
