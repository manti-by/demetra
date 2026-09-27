---
title:              MNT-193 — Mobile template for the React frontend
date: 2026-09-02
type: implementation
status: resolved
session_id: sess_3c168c00-25c9-41f5-b4bb-f0c70d0e67a3
services: [react-frontend, react]
branch: demetra/feature/mnt-193-mobile-template
tickets: [MNT-193, MNT-92, MNT-113]
tags: [frontend, react, mobile, responsive, css, media-queries, accessibility, inert, truncate, layout, markdown, marked, modal]
related:
- 2026-07-22-react-frontend-template-warp.md
- 2026-08-25-loader-styleguide.md
- 2026-06-02-truncate-session-name.md
- 2026-06-09-markdown-renderer.md
---

# MNT-193 — Mobile template for the React frontend

## TL;DR

Mobile-responsive template for `react/src` per MNT-193 (MNT-174 mockups adapted to `SessionSidebar`/`SessionList`/`LogConsole`/`Header`). ≤768px: session list becomes bottom-sheet drawer with searchable card list, console gets sticky scrollable tab bar + bottom Sessions bar, touch targets ≥44px, zero horizontal overflow. Desktop pixel-identical except status dot. PR #117; Cursor review added Escape dismissal and `inert` on background.

---

## Overview

One media query, no JS breakpoint detection. All mobile behavior behind single `@media (max-width: 768px)` at end of `App.css`; mobile-only elements `display:none` on desktop, sidebar wrapper `display:contents` so flex layout untouched. Only new React state: `sidebarOpen` boolean.

**File:** `react/src/App.tsx`

```tsx
const [sidebarOpen, setSidebarOpen] = useState(false);
const handleSelectSession = useCallback((taskId: string) => {
  setSelectedTaskId(taskId);
  setSidebarOpen(false);
}, []);
```

New DOM: overlay + `.sidebar-slot` (drawer) + `.console-container` with `.console-tabs` + `LogConsole` + `SessionArtifacts` + `.console-toolbar` (Sessions button).

## Desktop untouched — `display: contents`

**File:** `react/src/App.css`

```css
.sidebar-slot { display: contents; }
.sidebar-overlay, .console-tabs, .console-toolbar, .session-search { display: none; }
```

Inside media query `.sidebar-slot` becomes fixed bottom sheet (`translateY(100%)` + `visibility:hidden` when closed, `.open` slides up) with `::before` grab handle over `.sidebar-overlay` (`z-index 150/160`).

## Session list — search + cards

**File:** `react/src/components/SessionList.tsx`

Client-side filter via `useMemo` on `name/task_id/session_id/step/build_plan`; empty states split: "No sessions found" vs "No matching sessions". Each `SessionItem` gains colored `.session-dot.step-<step>` (desktop-visible too — only desktop delta). On mobile items restyle to cards (surface-2, border, radius, 44px min-height). Root `session-list-root` flex column keeps search above scroll container.

## Console — touch targets, overflow

**File:** `react/src/App.css` (`@media (max-width: 768px)`)

- `.console-tabs`: scrollable pills, `scrollbar-width:none`, active in accent-subtle.
- `.log-content { overflow-x:auto }` + `.log-message { white-space:pre }` — long lines scroll inside log, page never overflows (`body,#root { overflow-x:hidden }`, `scrollWidth===375` verified with drawer open).
- Touch targets: `.log-btn`, `.console-tab`, `.console-toolbar-btn`, `.session-search-input`, header icons `min-height/width 44px`; `.user-name` and `kbd` hint hidden; `app { height:100dvh }` fallback.
- Modals / command palette drop to bottom-sheet / full-width. Theme tokens (`--color-surface-*` etc.) reused, zero new colors.

## Test Results

- `bun run build` (tsc+vite): passes
- `bun run test`: 61/61 pass (9 files, 2 new SessionList search tests)
- `ruff` / `ty`: pass
- Browser (mock server): 390×844 tab bar/console/artifacts/Sessions bar OK, drawer search+cards OK, 375×812 `scrollWidth===375`, 1440×900 desktop unchanged.

---

## Review fixes — drawer accessibility (PR #117, commit `302b278`)

Two `ERROR` findings fixed:

1. **No keyboard dismissal:** added `window keydown` Escape effect scoped to `sidebarOpen` (mirrors `CommandPalette`).
2. **Background stays tab-focusable:** background containers get `inert` while open:

```tsx
const consoleInert = sidebarOpen ? { inert: "" } : {};
<header className="header" {...(inert ? { inert: "" } : {})} />
<div className="console-container" {...consoleInert}>
```

React 18 has no boolean `inert` prop (React 19) and `@types/react@18` doesn't type it — passed via JSX spread `inert=""` (presence matters). `Header` got `inert?: boolean` prop to avoid wrapper div breaking `position:sticky`.

## Follow-ups

- PR #117 merged to `master` (`302b278`/`832d912`/`111fdd8` on master 2026-09-03); Linear MNT-193 → Done.
- No swipe-to-dismiss (Escape/close button only); grab handle decorative.
- Tab bar renders all sessions scrollable; consider capping if large.
- Grouping by step not applicable — search+cards suffices.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-22-react-frontend-template-warp]], [[2026-08-25-loader-styleguide]]
- Source: Session truncation CSS [[2026-06-02-truncate-session-name]]; markdown via `marked ^15.0.12` [[2026-06-09-markdown-renderer]]
- External: [MNT-193](https://linear.app/mnt/issue/MNT-193/add-mobile-template-for-fe-app), [MNT-174](https://linear.app/mnt/issue/MNT-174/mobile-template), [PR #117](https://github.com/manti-by/demetra/pull/117)
