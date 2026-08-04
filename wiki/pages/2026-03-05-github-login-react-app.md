---
title: GitHub login for React app
date: 2026-03-05
type: implementation
status: resolved
session_id: -
services: [react, auth]
branch: -
tickets: [MNT-50]
tags: [auth, github, react, login]
related: []
---

# GitHub login for React app

## TL;DR

Added the client side of GitHub login to the React app: a GitHub sign-in button wired to the FastAPI auth API, a loading indicator while auth status is checked, and conditional rendering — a "Hello to Demetra" greeting for logged-in users versus a sign-in prompt for guests. GitHub button styling includes hover effects, and tests cover the loading + conditional rendering behavior.

---

## Overview

Follow-up to MNT-48 (backend GitHub OAuth). This ticket wires the frontend to the auth endpoints so users can log in and see a personalized greeting.

- Login service/component for the GitHub flow
- API request support wired to the FastAPI auth endpoints
- Loading indicator while checking auth status
- Conditional rendering: greeting vs sign-in prompt
- GitHub button styling with hover effects

## Step 1 — Login component and service

Added a GitHub login button and the service layer that calls the backend OAuth login endpoint from the React app.

## Step 2 — API request wiring

Wired the app's API request support to the FastAPI auth endpoints, replacing any stubbed/static auth behavior.

## Step 3 — Loading state

While the app checks the auth status on load, a loading indicator is shown instead of the login UI.

## Step 4 — Conditional rendering

- Logged in: "Hello to Demetra" greeting
- Guest: sign-in prompt with the GitHub button

## Step 5 — Button styling

Styled the GitHub button with hover effects to match the theme.

## Test Results

Tests validate the loading state and the conditional rendering (greeting for authenticated, sign-in prompt for guests).

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-50
