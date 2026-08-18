---
title: Add basic React app
date: 2026-03-04
type: implementation
status: resolved
session_id: -
services: [react]
branch: -
tickets: [MNT-49]
tags: [react, vite, bun, frontend]
related: []
---

# Add basic React app

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-07-22-react-frontend-template-warp]]. See wiki/archive/ for the
> original.

## TL;DR

Scaffolded the Demetra frontend as a TypeScript + Vite React app under `react/`, built and run with `bun`, showing a single H1 header page in the grey/green/dark-green/black theme. Bundled tooling (Makefile targets, `.gitignore`, README), Vitest + testing-library unit tests, and a systemd service to host the built app.

---

## Overview

First frontend milestone: a minimal but fully tooled React app that establishes the theme, build pipeline, and hosting before feature work (login, sessions) starts.

- React (TypeScript) app scaffolded with Vite, built/run with `bun`
- Single-page app with an H1 header
- Theme colors: grey, green, dark-green, black
- Unit tests via Vitest + testing-library
- systemd service for hosting the built app

## Step 1 — Scaffold the app

Created the frontend in `react/` using Vite with TypeScript. Build and run flows use `bun` for install, dev, and build steps.

## Step 2 — Single page and theme

Added a single page with an H1 header and applied the theme palette (grey / green / dark-green / black) to establish the visual identity.

## Step 3 — Tooling and secondary files

**File:** `Makefile`, `.gitignore`, `react/`

- Makefile targets: `react`, `react-install`, `react-build`, `react-test`
- `.gitignore` entries for `node_modules` and build output
- README updates covering the new frontend commands

## Step 4 — Hosting

Added a systemd service definition to host the built React app.

## Test Results

Unit tests via Vitest + testing-library cover the scaffolded components.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-49
