---
title:              Favicon Set for the React App
date:               2026-08-03
type:               implementation
status:             resolved
session_id:         "-"
services:           [react]
branch:             "-"
tickets:            []
tags:               [frontend, favicon, icons, branding, react, vite]
related: [2026-07-22-react-frontend-template-warp.md]
---

# Favicon Set for the React App

## TL;DR

Generated a full favicon set (`.ico` + PNGs + PWA manifest) from `media/logo.svg` and wired it into `react/index.html`. `cairosvg` failed (no system cairo), so `sharp` (bundles libvips+librsvg, zero system deps) rasterized in a throwaway temp dir; `sharp` can't emit ICO, so `favicon.ico` was hand-assembled from 16/32/48 PNGs. Verified with `file` + `vite build`.

## Overview

| Layer | Change |
|-------|--------|
| Assets | `react/public/` → `favicon.ico`, `favicon-16/32.png`, `apple-touch-icon.png`, `android-chrome-192/512.png` |
| Manifest | `site.webmanifest` (icons, `theme_color`/`background_color` `#25292e`) |
| HTML | `react/index.html:7-12` icon/manifest/theme-color links |
| Build | `vite build` copies `public/`→`dist/` |

## Step 1 — Tooling

`media/logo.svg` — `viewBox 0 0 83.38 83.38`, `#25292e` rect + white path. No rasterizer on machine (`rsvg-convert`/`convert`/`inkscape`/`sips` absent). `uv run --with cairosvg` → `OSError: no library called "cairo-2"`. Fallback: `sharp` in `/var/folders/.../T/opencode/favicon-build` (outside repo, no `react/package.json` change).

## Step 2 — Rasterize to PNG

```js
for (const [name, size] of Object.entries({"favicon-16x16.png":16,"favicon-32x32.png":32,"apple-touch-icon.png":180,"android-chrome-192x192.png":192,"android-chrome-512x512.png":512}))
  await sharp(svg).resize(size,size).png().toFile(path.join(outDir,name));
```

## Step 3 — Hand-assemble `favicon.ico`

`sharp` `toFormat("ico")` throws unsupported format. Built ICO container manually: `ICONDIR` header (6 bytes) + 3× `ICONDIRENTRY` (16 bytes each) + raw PNG payloads (PNG-compressed entries accepted by browsers). Result 1060 bytes, `file` → `MS Windows icon resource - 3 icons`.

## Step 4 — Webmanifest

**`react/public/site.webmanifest`:**

```json
{"name":"Demetra","short_name":"Demetra","icons":[{"src":"/android-chrome-192x192.png","sizes":"192x192"},{"src":"/android-chrome-512x512.png","sizes":"512x512"}],"theme_color":"#25292e","background_color":"#25292e","display":"standalone"}
```

Colors from logo square `media/logo.svg` `.cls-1{fill:#25292e}`.

## Step 5 — Wire into `react/index.html:7-12`

```html
<link rel="icon" href="/favicon.ico" sizes="48x48" />
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<link rel="manifest" href="/site.webmanifest" />
<meta name="theme-color" content="#25292e" />
```

Vite serves `public/` at `/`, paths are root-relative.

## Step 6 — Cleanup

Removed `_favicon-*.png` temps from failed cairosvg attempt. `favicon-build` temp dir left for reuse (only `sharp` install).

## Test Results

`file` confirms all PNGs + ICO; `vite build` 59 modules, 401ms, `dist/` contains all assets beside `index.html`. Visual glyph not verified in-session (trivial rect+path, minimal risk).

## Follow-ups

- Eyeball favicon in browser / iOS home screen after deploy.
- If BMP ICO entries needed, rebuild with Pillow `Image.save(format="ICO")`.

## References

- [[2026-07-22-react-frontend-template-warp]] — warp theme / React context
- `media/logo.svg` — source (1-line SVG, `#25292e` + white path)
- `react/index.html` · `react/public/` (Vite static root at `/`)
