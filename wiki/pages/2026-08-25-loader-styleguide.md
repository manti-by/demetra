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

Replaced every BE-waiting indicator in the React app with the new `react/public/loader.svg` via a reusable `Loader` component, and added a living Style Guide at `/styleguide` linked from the burger menu that catalogs all existing UI primitives and composites.

> **Consistency note (2026-08-28, Consistency Agent):** Frontmatter `branch: -` was unquoted YAML (parsed as a sequence); quoted to `"-"` per wiki template convention.

---

## Overview

Two requests in one session:

- **Loader:** repo already contained `react/public/loader.svg` (olive #788860 animated circles). Every text or CSS spinner shown while awaiting a backend response had to be replaced with that asset.
- **Style guide:** add a browseable page that demonstrates every existing component so the loader (and future changes) can be inspected visually without breaking FE/BE, plus a burger-menu entry to reach it.

## Step 1 — Reusable Loader component

**File:** `react/src/components/Loader.tsx:1`

```tsx
interface LoaderProps { size?: number; fullScreen?: boolean; className?: string; alt?: string; }
export function Loader({ size = 48, fullScreen = false, className, alt = "Loading..." }: LoaderProps) {
  return (
    <div className={`loader-container ${fullScreen ? "loader-fullscreen" : ""} ${className ?? ""}`.trim()}>
      <img src="/loader.svg" alt={alt} width={size} height={size} className="loader-image" />
    </div>
  );
}
```

**File:** `react/src/App.css:556`

- Added `.loader-container` (flex centering, `padding: 1.5rem`), `.loader-fullscreen` (`min-height: 100vh`, `background: var(--color-canvas)`), `.loader-image` (`display:block; object-fit:contain`).
- Collapsed padding for inline button usage: `.auth-submit .loader-container, .btn-primary .loader-container { padding:0; display:inline-flex; }`
- Kept legacy `.loading-container` / `.loading-spinner` / `.callback-spinner` as backwards-compat aliases (same border/spin rules).

Why an `<img>` and not inline SVG: the asset is already public, Vite serves `/loader.svg` as static, and the animation is defined inside the SVG via `<animateTransform>` — no CSS needed. `size` controls both `width`/`height` attributes for crisp scaling.

## Step 2 — Replace all BE-waiting spinners/text

Search was `Loading|loading|spinner|callback-spinner` + manual inspection of `react/src`:

- **File:** `react/src/App.tsx:27` — `LoadingSpinner()` now `return <Loader fullScreen size={56} />`; `Suspense fallback` now `<Loader size={48} />`.
- **File:** `react/src/components/SessionList.tsx:1,81` — `Loading sessions...` text → `<Loader size={36} />`.
- **File:** `react/src/components/ProjectList.tsx:9,146,241` — loading container/spinner → `<Loader size={40} />`; `Creating...` button text while `saving` → `<Loader size={18} />`.
- **File:** `react/src/components/SessionHistory.tsx:2,181` — `<div className="loading-spinner" />` → `<Loader size={36} />`.
- **File:** `react/src/components/EnvSettings.tsx:9,213,267` — same + `Saving...` → `<Loader size={18} />`.
- **File:** `react/src/components/SharedEnvSettings.tsx:9,178,233` — same pattern.
- **File:** `react/src/pages/GitHubCallback.tsx:3,40` — `callback-spinner` div + `Authenticating...` text → `<Loader size={48} />` (still inside `.callback-page`/`.callback-content` for centering).
- **File:** `react/src/components/PasswordAuthForm.tsx:3,62` — `Please wait...` → `<Loader size={20} />` inside `.auth-submit`.

Updated tests to match new DOM:

- **File:** `react/src/components/SessionHistory.test.tsx:82` — `document.querySelector('.loading-spinner')` → `screen.getByAltText('Loading...')`.
- **File:** `react/src/components/SessionList.test.tsx:22` — `getByText('Loading sessions...')` → `getByAltText('Loading...')`.

Build and tests green: `vite build` (65 modules), `vitest` 49 passed.

## Step 3 — Style Guide page

**File:** `react/src/pages/StyleGuide.tsx:1` — self-contained catalog, no BE calls. Sections:

- **Loader** — grid of sizes 18/28/40/56, button-inline demo, fullscreen mock box.
- **Design Tokens** — swatches for `canvas/surface-1-2-3`, accent/success/error/warning, text colors.
- **Typography** — h1–h6, p, small, code/kbd/blockquote/pre.
- **Buttons** — primary/secondary/disabled/loader-inline, btn-icon, theme-toggle, palette-trigger, github-login-button.
- **Forms** — form-input, env-form row (key/value + encrypted checkbox), settings-error.
- **Sessions & Projects** — session-item variants (selected/build/completed/failed/initial), step badges, project-item, env-row, empty states.
- **Log Console** — live header+lines+error/success + empty states statically rendered.
- **Session History** — inline timeline/totals + live `<SessionHistory>` modal demo (populated / loading toggle via local state, mock entries `MOCK_HISTORY_ENTRIES`).
- **Modals** — inline build-plan modal shell + live overlay demo.
- **Auth & misc** — GitHub button, auth fields, artifacts links, user-info/avatar.

Mock data is local; interactive toggles (`showHistory`, `showModal`, `historyLoading` with 1.5s timeout) let the loader be seen without delaying real APIs.

**File:** `react/src/pages/StyleGuide.css:1` — layout only (max-width 1100, `.styleguide-header`, `.sg-section`, `.sg-card`, `.sg-loader-grid`, `.sg-swatches`, `.sg-form-grid`, responsive 2-col collapse).

## Step 4 — Routing and burger menu

**File:** `react/src/App.tsx:17,108`

```tsx
const StyleGuide = lazy(() => import("./pages/StyleGuide").then(m => ({ default: m.StyleGuide })));

function StyleGuideLayout() {
  const { user, loading, logout } = useAuth();
  const handleLogout = useCallback(async () => { await logout(); window.location.reload(); }, [logout]);
  if (loading) return <LoadingSpinner />;
  return (
    <div className="app">
      <Header user={user} onLogout={handleLogout} />
      <main className="main-content">
        <Suspense fallback={<Loader size={48} />}><StyleGuide /></Suspense>
      </main>
    </div>
  );
}
// inside <Routes>
<Route path="/styleguide" element={<StyleGuideLayout />} />
```

`StyleGuideLayout` reuses `Header` + `AuthContext` so the burger remains available on the guide. Anonymous users can still open `/styleguide` (header shows without burger) — no login gate.

**File:** `react/src/components/Header.tsx:2,164`

- Added `import { Link } from "react-router-dom"`.
- Prepended burger menu item:

```tsx
<Link to="/styleguide" onClick={() => setMenuOpen(false)}>
  <svg>…grid 2×2…</svg> Style guide
</Link>
```

Placed after RQ Dashboard and before Logout in the burger menu (`react/src/components/Header.tsx:167-196`): Settings → Shared environment → RQ Dashboard → Style guide → Logout.

> **Consistency note (2026-08-27, Consistency Agent):** Corrected the Step 3 placement claim — an earlier draft said "above Settings/Shared env, before RQ Dashboard"; the committed order is Style guide after RQ Dashboard.

## Test Results

- **File:** `react` — `npm run build` — `tsc && vite build` → 65 modules, gzip ~93k JS, no type errors.
- **File:** `react` — `npm test -- --run` → 8 test files, 49 tests passed, 0 failed.

## Follow-ups

- Consider screenshot/visual-regression check for the loader (e.g., Playwright `toHaveScreenshot` on `/styleguide` loader grid) so future CSS changes don't silently break animation.
- If more BE-waiting states appear, reuse `<Loader>` rather than adding new CSS spinners — the legacy `.loading-spinner`/`.callback-spinner` aliases can be removed once no call sites reference them.
- Style guide could be extended with `CommandPalette` live demo and theme toggle matrix once those components get more variants.

## References

- Related: [[2026-07-22-warp-theme-review-fixes-and-ops]] — Warp theme + green accent palette that defines the tokens shown in the guide
- Related: [[2026-07-23-session-history-modal]] — Session History modal that the guide demonstrates
- Related: [[2026-07-22-react-frontend-template-warp]] — Frontend layout/template that the guide's project/session/log sections reflect
- External: `react/public/loader.svg` — animated circles, `fill='#788860' stroke='#788860' stroke-width='5'`
