---
title: 'MNT-225: Add copy button'
date: '2026-09-27'
type: implementation
status: resolved
session_id: ses_f1dd57f7dffeGEATu4YXakfdTP
services: [react]
branch: mnt-225-add-copy-button
tickets: [MNT-225]
tags: [wiki, feature, frontend]
related: [2026-06-09-build-artifacts.md, 2026-06-09-markdown-renderer.md]
---
# MNT-225: Add copy button

## TL;DR

A 'Copy' button has been added to the build plan modal footer, allowing users to copy the raw markdown text to the clipboard. The implementation includes feature detection for the clipboard API and feedback for the user. All tests have passed, and the necessary React components and wiki pages have been updated.

---

## Overview

The `SessionArtifacts.tsx` component has been extended to include the new 'Copy' button, which uses the `navigator.clipboard.writeText()` API to copy the markdown text. The `SessionArtifacts.test.tsx` file has been updated with new test cases, and a wiki page has been created to document the implementation details.

## Changed files

- `react/src/components/SessionArtifacts.tsx` — `Copy` button in the build plan modal footer, clipboard feature detection, 1.5s "Copied!" feedback, and invalidation of a pending copy when the modal closes.
- `react/src/components/SessionArtifacts.test.tsx` — tests for Copy button rendering, clipboard write, unavailable clipboard API, and a pending copy resolving after close.
- `wiki/INDEX.md` — index entry for this page under `Pages` and `React frontend / UI`.
- `wiki/pages/2026-09-27-mnt-225-add-copy-button.md` — this page.

## Stat

```text
react/src/components/SessionArtifacts.test.tsx   | 90 +++++++-
react/src/components/SessionArtifacts.tsx       | 41 ++++++-
wiki/INDEX.md                                   | 3 +-
wiki/pages/2026-09-27-mnt-225-add-copy-button.md | 125 ++++++++++
4 files changed, 259 insertions(+), 3 deletions(-)
```

## Build plan

## Implementation Plan
### Approach
The plan is to add a "Copy" button to the existing build-plan modal footer in `SessionArtifacts.tsx`. This button will copy the raw markdown text of the build plan to the clipboard when clicked and display "Copied!" as feedback for 1.5 seconds.

### Key Technical Decisions
- The `navigator.clipboard.writeText()` API will be used to write the markdown text to the clipboard.
- Feature detection will be implemented to handle cases where the clipboard API is unavailable.
- The `SessionArtifacts.tsx` component will be extended to include the new "Copy" button and related functionality.

### Implementation Steps
1. **Update `SessionArtifacts.tsx`**:
   - Add a `copied` state and a `copyResetRef` to track the feedback-reset timeout.
   - Implement the `handleCo…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f1dd57f7dffeGEATu4YXakfdTP`

---

## Follow-ups

- None

## References

- Related: [[2026-06-09-build-artifacts]], [[2026-06-09-markdown-renderer]]
- External: https://linear.app/mnt/issue/MNT-225/add-copy-button

> **Consistency fix (2026-09-28, Consistency Agent):** mirrored `related:` into the body; trimmed the ~150-entry `services:` filename dump to subsystem tags.
