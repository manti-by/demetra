---
title:              MNT-193 — Mobile template for the React frontend
date: 2026-09-02
type: implementation
status: resolved
session_id: sess_3c168c00-25c9-41f5-b4bb-f0c70d0e67a3
services: [react-frontend]
branch: demetra/feature/mnt-193-mobile-template
tickets: [MNT-193]
tags: [frontend, react, mobile, responsive, css, media-queries, accessibility, inert]
related: [2026-07-22-react-frontend-template-warp.md, 2026-08-25-loader-styleguide.md]
---

# MNT-193 — Mobile template for the React frontend

## TL;DR

Implemented the mobile-responsive template for the React app (`react/src`) per MNT-193, adapting the MNT-174 mockups (session tab bar, "Recent connections" list, console-first screen) to Demetra's `SessionSidebar` / `SessionList` / `LogConsole` / `Header`. On viewports ≤768px the session list becomes a bottom-sheet drawer with a searchable card list, the console gains a sticky horizontally-scrollable session tab bar plus a bottom Sessions action bar, touch targets are ≥44px, and the page has zero horizontal overflow. Desktop is pixel-identical apart from a small status dot added to session items. Opened as [PR #117](https://github.com/manti-by/demetra/pull/117). After a Cursor PR review round, the drawer also gained keyboard dismissal (Escape) and background content is marked `inert` while it is open.

---

## Overview

Design constraint chosen up front: **one media query, no JS breakpoint detection**. All mobile behavior lives behind a single `@media (max-width: 768px)` block at the end of `App.css`; every mobile-only element is `display: none` on desktop, and the sidebar wrapper uses `display: contents` there so the existing flex layout is untouched. The only new React state is a boolean for the drawer.

**File:** `react/src/App.tsx`

```tsx
const [sidebarOpen, setSidebarOpen] = useState(false);

const handleSelectSession = useCallback((taskId: string) => {
  setSelectedTaskId(taskId);
  setSidebarOpen(false);   // drawer closes on selection; harmless no-op on desktop
}, []);
```

New DOM slots in the authenticated tree:

```tsx
{sidebarOpen && <div className="sidebar-overlay" onClick={handleCloseSidebar} />}
<div className={`sidebar-slot${sidebarOpen ? " open" : ""}`}>
  <SessionSidebar ... />
</div>
<div className="console-container">
  <div className="console-tabs"> {/* per-session pill tabs, like odin/amon-ra */} </div>
  <LogConsole ... />
  <SessionArtifacts ... />
  <div className="console-toolbar"> {/* bottom action bar: Sessions (N) */} </div>
</div>
```

## Step 1 — Desktop stays untouched via `display: contents`

**File:** `react/src/App.css`

```css
.sidebar-slot { display: contents; }   /* aside stays a direct flex child on desktop */

.sidebar-overlay,
.console-tabs,
.console-toolbar { display: none; }    /* mobile-only elements */

.session-search { display: none; }     /* mobile-only search */
```

`display: contents` makes the wrapper vanish from layout, so `aside.session-sidebar` keeps its exact old geometry on desktop. Inside the media query the same `.sidebar-slot` becomes a fixed bottom sheet (`transform: translateY(100%)` + `visibility: hidden` when closed, `.open` slides it up) with a `::before` grab handle, over a fixed `.sidebar-overlay` at `z-index: 150/160`.

## Step 2 — Session list ergonomics (search + cards)

**File:** `react/src/components/SessionList.tsx`

Added a search input and a client-side filter; the list root became a `session-list-root` flex column so the search bar sits above the scroll container without breaking the sidebar's `flex: 1; min-height: 0` chain:

```tsx
const filteredSessions = useMemo(() => {
  const q = query.trim().toLowerCase();
  if (!q) return sessions;
  return sessions.filter((session) =>
    [session.name, session.task_id, session.session_id, session.step, session.build_plan].some(
      (value) => (value ?? '').toLowerCase().includes(q),
    ),
  );
}, [sessions, query]);
```

Empty states split: "No sessions found" (no data) vs "No matching sessions" (filter). Each `SessionItem` gained a colored status dot (`.session-dot.step-<step>`, reusing the `session-step` color ladder) — visible on desktop too, the one intentional desktop delta. On mobile, `.session-item` restyles into a card (surface-2 background, border, radius, 44px min-height).

## Step 3 — Console ergonomics, touch targets, overflow

**File:** `react/src/App.css` (`@media (max-width: 768px)` block)

- `.console-tabs`: horizontally scrollable pill row, `scrollbar-width: none`, active tab in accent-subtle; clicking a tab selects that session (state already lives in `App`).
- `.log-content { overflow-x: auto }` + `.log-message { white-space: pre }` — long terminal lines scroll horizontally inside the log area (as in the mockup) instead of wrapping; the page itself never overflows (`body, #root { overflow-x: hidden }`, verified `scrollWidth === 375` with the drawer open).
- Touch targets: `.log-btn`, `.console-tab`, `.console-toolbar-btn`, `.session-search-input` get `min-height: 44px`; header icon buttons get `min-width/min-height: 44px`; `.user-name` and the palette `kbd` hint are hidden.
- `.app { height: 100dvh }` fallback added next to the existing `100vh` for mobile browser chrome.
- Modals and the command palette drop to bottom-sheet / near full-width.

Theme reuse: everything consumes the existing `ThemeContext` tokens (`--color-surface-*`, `--color-accent`, `--radius-*`), so the dark theme matches the mockups with zero new colors.

## Test Results

- `bun run build` (tsc + vite): passes.
- `bun run test`: **61/61 pass** across 9 files, including 2 new `SessionList` tests (search filters the list; "No matching sessions" empty state).
- `uv run ruff check` / `uv run ty check`: pass (no Python touched).
- Browser verification against a local mock server (built `dist/` + stubbed `/api/v1/github/me` and `/api/v1/sessions`):
  - 390×844 — tab bar, console, artifacts row, bottom Sessions bar render; no overflow.
  - Drawer — search input + card list (dot, title, step badge, subtitle); tapping `amon-ra` closes the drawer and activates its tab.
  - 375×812 — `document.scrollWidth === 375` even with the drawer open.
  - 1440×900 — desktop layout unchanged.

---

## Review fixes — drawer accessibility (PR #117)

The Cursor PR-review automation requested changes on [PR #117](https://github.com/manti-by/demetra/pull/117) with two `ERROR` findings about the mobile drawer; both were accepted and fixed in commit `302b278`.

**1. No keyboard dismissal** — the bottom sheet was tap-only (previously listed as a follow-up). Added a `window` `keydown` effect scoped to `sidebarOpen`, mirroring the `CommandPalette` Escape pattern:

```tsx
useEffect(() => {
  if (!sidebarOpen) return;
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") setSidebarOpen(false);
  };
  window.addEventListener("keydown", handleKeyDown);
  return () => window.removeEventListener("keydown", handleKeyDown);
}, [sidebarOpen]);
```

**2. Background content stays tab-focusable** — with the drawer open, keyboard users could Tab into header and console controls underneath the overlay (it only handled clicks). Both background containers now get the `inert` attribute while `sidebarOpen` is true:

```tsx
const consoleInert = sidebarOpen ? { inert: "" } : {};
// Header gains an optional `inert` prop forwarded to its root:
<header className="header" {...(inert ? { inert: "" } : {})} />
<div className="console-container" {...consoleInert}>
```

React 18 gotcha worth remembering: React 18 has no boolean `inert` prop support (that landed in React 19) and `@types/react@18` does not type it, so the string form is passed through a JSX spread (`inert=""` — presence of the attribute is what matters to the browser). `Header` was extended with an `inert?: boolean` prop rather than wrapping the header in a div, which would have broken its `position: sticky` behavior.

Verification after the fix: `tsc --noEmit` clean, 61/61 tests still pass. Desktop is unaffected — `sidebarOpen` can only become true from the mobile-only toolbar button.

---

## Follow-ups

- PR #117 awaits review/merge; Linear ticket MNT-193 should move to In Review with the PR (done by hand — no Linear access from this session).
- Drawer has no swipe-to-dismiss gesture (Escape and the close button work); the grab handle is decorative.
- Session tab bar renders all sessions (scrollable); consider capping/most-recent if lists grow large.
- Grouping of the session list (e.g. by step) was deemed not applicable for now — search + cards covers the acceptance criterion.

## References

- Related: [[2026-07-22-react-frontend-template-warp]] (the Warp-inspired desktop template this extends)
- Related: [[2026-08-25-loader-styleguide]] (style guide page for the UI primitives reused here)
- External: [MNT-193](https://linear.app/mnt/issue/MNT-193/add-mobile-template-for-fe-app), [MNT-174](https://linear.app/mnt/issue/MNT-174/mobile-template), [PR #117](https://github.com/manti-by/demetra/pull/117)
