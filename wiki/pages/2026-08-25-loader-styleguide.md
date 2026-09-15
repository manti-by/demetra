---
title: Loader replacement and Style Guide page
date: 2026-08-25
type: implementation
status: resolved
session_id: ses_8f3a2b1c-20260825
services: [react]
branch: "-"
tickets: []
tags: [loader, styleguide, frontend, burger-menu]
related: [2026-07-22-warp-theme-review-fixes-and-ops.md, 2026-07-23-session-history-modal.md, 2026-07-22-react-frontend-template-warp.md]
---

# Loader replacement and Style Guide page

## TL;DR

Replaced all backend-waiting spinners with `react/public/loader.svg` (olive #788860) via a reusable `Loader` component, and added a living Style Guide at `/styleguide` linked from the burger menu cataloging all UI primitives/composites.

> **Consistency note (2026-08-28, Consistency Agent):** Frontmatter `branch: -` quoted to `"-"` per template convention.

## Loader component

`react/src/components/Loader.tsx:1` — `Loader({ size=48, fullScreen=false, className, alt="Loading..." })` renders `<img src="/loader.svg" width={size} height={size}>` inside `.loader-container` (`<animateTransform>` is inside the SVG, no CSS needed).

`react/src/App.css:556` — `.loader-container` (flex centering, `padding:1.5rem`), `.loader-fullscreen` (`min-height:100vh`), `.loader-image` (block/contain); inline-button collapse for `.auth-submit/.btn-primary`; legacy `.loading-spinner` aliases kept.

## Spinner replacement

Search `Loading|loading|spinner|callback-spinner` + manual inspection across `react/src`:

- `App.tsx:27` — `LoadingSpinner()` → `<Loader fullScreen size={56}/>`, `Suspense fallback` → `<Loader size={48}/>`
- `SessionList.tsx:1,81` — `Loading sessions...` → `<Loader size={36}/>`
- `ProjectList.tsx:9,146,241` — loading spinner → `<Loader size={40}/>`; `Creating...` while saving → `<Loader size={18}/>`
- `SessionHistory.tsx:2,181` — `loading-spinner` div → `<Loader size={36}/>`
- `EnvSettings.tsx:9,213,267` / `SharedEnvSettings.tsx:9,178,233` — same
- `GitHubCallback.tsx:3,40` — `callback-spinner` + `Authenticating...` → `<Loader size={48}/>`
- `PasswordAuthForm.tsx:3,62` — `Please wait...` → `<Loader size={20}/>`

Tests: `SessionHistory.test.tsx:82` (`querySelector('.loading-spinner')` → `getByAltText('Loading...')`), `SessionList.test.tsx:22` (`getByText` → `getByAltText`). `vite build` 65 modules, `vitest` 49 passed.

## Style Guide page

`react/src/pages/StyleGuide.tsx:1` — no BE calls, local mock data + toggles (`showHistory`/`showModal`/`historyLoading` 1.5s). Sections: Loader (18/28/40/56 + button-inline + fullscreen mock), Design Tokens (canvas/surface/accent/success/error/warning/text), Typography, Buttons, Forms, Sessions & Projects (session-item variants, step badges, empty states), Log Console, Session History (inline + live `<SessionHistory>` demo), Modals, Auth & misc.

`react/src/pages/StyleGuide.css:1` — layout (max-width 1100, `.sg-section`/`.sg-card`/`.sg-loader-grid`/`.sg-swatches`, responsive 2-col).

## Routing & burger menu

`react/src/App.tsx:17,108` — lazy `StyleGuide`, `StyleGuideLayout` (reuses `Header`+`AuthContext`, `Suspense fallback={<Loader>}`), `<Route path="/styleguide" element={<StyleGuideLayout/>}/>` — anonymous accessible.

`react/src/components/Header.tsx:2,164` — added `Link` import, burger entry `<Link to="/styleguide">Style guide</Link>` ordered Settings → Shared env → RQ Dashboard → Style guide → Logout.

> **Consistency note (2026-08-27):** Earlier draft misstated placement as above Settings; committed order is after RQ Dashboard.

## Test Results

- `npm run build` — `tsc && vite build` → 65 modules, gzip ~93k JS
- `npm test -- --run` → 8 files, 49 passed

## Follow-ups

- Consider Playwright `toHaveScreenshot` for loader grid; reuse `<Loader>` for future waiting states; legacy spinner aliases removable once unreferenced; extend guide with `CommandPalette`/theme matrix.

## References

- Related: [[2026-07-22-warp-theme-review-fixes-and-ops]], [[2026-07-23-session-history-modal]], [[2026-07-22-react-frontend-template-warp]]
- External: `react/public/loader.svg` (`fill='#788860'`)
