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

Generated a full favicon set (`.ico` + PNGs + PWA webmanifest) from the existing `media/logo.svg` and wired it into `react/index.html`. The source SVG is a dark `#25292e` square with a white glyph, so the `theme-color` and manifest colors are taken from the logo. `cairosvg` was unusable (no system cairo lib), so rendering was done with `sharp` (bundles libvips + librsvg) in a throwaway temp dir; `sharp` can't emit ICO, so the multi-size `favicon.ico` was assembled by hand from 16/32/48 PNGs. Verified with `file` and a full `vite build`.

---

## Overview

| Layer      | Change                                                                                    |
| ---------- | ----------------------------------------------------------------------------------------- |
| Assets     | `react/public/` gets `favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png`, `android-chrome-192x192.png`, `android-chrome-512x512.png` |
| Manifest   | New `react/public/site.webmanifest` (PWA icons, theme/background color)                   |
| HTML       | `react/index.html` gains icon links, `apple-touch-icon`, `manifest`, and `theme-color`    |
| Build      | `vite build` copies `public/` to `dist/` unchanged; HTML references `/favicon.ico` etc.    |

---

## Step 1 — Tooling check

`media/logo.svg` is a 1-line SVG (`viewBox="0 0 83.38 83.38"`): a `#25292e` rect with a white speech-bubble-ish path. No SVG rasterizer on the machine (`rsvg-convert`/`convert`/`inkscape` absent; `sips` doesn't handle SVG; no `sharp` in `react/node_modules`).

`uv run --with cairosvg` failed with `no library called "cairo-2" was found` — cairosvg needs the system cairo C library, which isn't installed:

```python
OSError: no library called "cairo-2" was found
```

Fallback: install `sharp` in `/var/folders/.../T/opencode/favicon-build` (outside the repo so `react/package.json` stays untouched). `sharp` bundles libvips with its own librsvg, so it rasterizes SVG with zero system deps.

---

## Step 2 — Rasterize the logo to PNG sizes

**File:** `react/public/*.png` (new)

```js
const sizes = {
  "favicon-16x16.png": 16,
  "favicon-32x32.png": 32,
  "apple-touch-icon.png": 180,
  "android-chrome-192x192.png": 192,
  "android-chrome-512x512.png": 512,
};
for (const [name, size] of Object.entries(sizes)) {
  await sharp(svg).resize(size, size).png().toFile(path.join(outDir, name));
}
```

---

## Step 3 — Build `favicon.ico` manually

`sharp`'s `toFormat("ico", ...)` throws `Expected one of: heic, heif, ... for format but received ico` — ICO output isn't supported. Since browsers accept PNG-compressed entries in `.ico`, the container was assembled by hand:

- `ICONDIR` header (6 bytes: reserved=0, type=1, count=3)
- One 16-byte `ICONDIRENTRY` per size (width, height, planes=1, bitCount=32, byte length, file offset)
- Then the raw 16/32/48 PNG payloads

Result: a valid `MS Windows icon resource - 3 icons` (confirmed via `file favicon.ico`), 1060 bytes.

---

## Step 4 — PWA webmanifest

**File:** `react/public/site.webmanifest` (new)

```json
{
  "name": "Demetra",
  "short_name": "Demetra",
  "icons": [
    { "src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png" }
  ],
  "theme_color": "#25292e",
  "background_color": "#25292e",
  "display": "standalone"
}
```

`#25292e` is the logo's square color (`media/logo.svg`, `.cls-1{fill:#25292e}`), so theme/background match the brand mark.

---

## Step 5 — Wire into `react/index.html`

**File:** `react/index.html:7-12`

```html
<link rel="icon" href="/favicon.ico" sizes="48x48" />
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<link rel="manifest" href="/site.webmanifest" />
<meta name="theme-color" content="#25292e" />
```

Order follows the real favicon-style convention: `.ico` for legacy browsers, PNG for modern (16/32), apple-touch-icon (180) for iOS home screen, webmanifest for Android/PWA. Vite serves `react/public/` at `/` so all paths are root-relative.

---

## Step 6 — Cleanup

The first (failed cairosvg→sharp) run left `_favicon-*.png` temp files in `public/`; removed with `rm`. The `favicon-build` temp dir was left for reuse but contains only the `sharp` install.

---

## Test Results

```shell
$ file favicon.ico favicon-16x16.png favicon-32x32.png apple-touch-icon.png android-chrome-192x192.png android-chrome-512x512.png
favicon.ico:                MS Windows icon resource - 3 icons, 16x16 ... 32x32 ... (PNG data)
favicon-16x16.png:          PNG image data, 16 x 16, 8-bit/color RGBA
favicon-32x32.png:          PNG image data, 32 x 32, 8-bit/color RGBA
apple-touch-icon.png:       PNG image data, 180 x 180, 8-bit/color RGBA
android-chrome-192x192.png: PNG image data, 192 x 192, 8-bit/color RGBA
android-chrome-512x512.png: PNG image data, 512 x 512, 8-bit/color RGBA

$ cd react && npx vite build
✓ 59 modules transformed.
dist/index.html                           1.18 kB │ gzip:  0.55 kB
✓ built in 401ms
```

`dist/` now contains all favicon assets + `site.webmanifest` next to `index.html`, confirming the `public/`→`dist/` copy. Visual inspection of the rendered glyph is the one thing not verified in-session (no image input available) — the source is a trivial rect+path, so risk is minimal.

---

## Follow-ups

- Eyeball the favicon in a browser tab (and iOS home screen via `apple-touch-icon.png`) once the app is deployed.
- If the `.ico` needs Windows-Vista-era BMP entries instead of PNG-compressed ones, rebuild with a proper ICO encoder (Pillow's `Image.save(..., format="ICO")` handles it).

## References

- [[2026-07-22-react-frontend-template-warp]] — warp theme / React frontend context
- `media/logo.svg` — source artwork (1-line SVG, `#25292e` square + white path)
- `react/index.html` — edited head
- `react/public/` — Vite static-asset root (served at `/`)
