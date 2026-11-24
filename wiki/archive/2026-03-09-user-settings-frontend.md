---
title: Add user setting to the frontend app
generated: {by: demetra, at: '2026-03-09T00:00:00Z'}
description: 'Records MNT-57, the React frontend companion to MNT-56: a user-settings component with a `keys` group lets users add key/value pairs and PATCHes them as a data dictionary to the user-update API, giving a UI for stored API keys; the page was later archived and merged into the React template page.'
type: implementation
status: deprecated
session_id: '-'
services: [react, api]
branch: '-'
tickets: [MNT-57]
tags: [react, user-settings, keys]
related: []
---

# Add user setting to the frontend app

> **Archived on 2026-08-18.** Useful info merged into
> [2026-07-22-react-frontend-template-warp](/pages/2026-07-22-react-frontend-template-warp.md). See wiki/archive/ for the
> original.

## TL;DR

Added a user-settings component to the React app with a `keys` group where key/value pairs can be added. Changes are sent as a PATCH to the user update API (from MNT-56) as a data dictionary, giving users a UI to manage their stored API keys.

---

## Overview

Frontend companion to MNT-56 (encrypted user settings on the backend). The component renders the current keys, lets the user add key/value pairs, and pushes them to the backend.

- user-settings component with a `keys` group
- Key/value pairs can be added in the UI
- Data sent as a PATCH to the user update API as a data dictionary

## Step 1 — user-settings component

Added a settings component to the React app containing a `keys` group where users can view and add key/value entries.

## Step 2 — PATCH to the user update API

On save, the component builds a data dictionary from the edited keys and sends it as a PATCH to the user update API from MNT-56.

## Test Results

Tests were added for the user-settings component.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-57
