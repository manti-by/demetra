---
title: 'CH-6: Markdown renderer'
date: '2026-11-06'
type: implementation
status: resolved
session_id: ses_e4f46534effeBppQxjkS76DkdH
services: [pyproject, App, ChatPanel.test, ChatPanel, MarkdownContent.test, MarkdownContent, SessionArtifacts.test, SessionArtifacts, SessionList.test, ChatPage.test, .sessions, INDEX, 2026-11-06-ch-6-markdown-renderer]
branch: ch-6-markdown-renderer
tickets: [CH-6]
tags: [wiki, frontend, feature]
related: [2026-06-09-markdown-renderer.md, 2026-11-03-ch-2-single-unified-session-view.md]
---

# CH-6: Markdown renderer

## TL;DR
This session implemented a markdown renderer for chat blocks, including descriptions, build plans, research plans, questions, and user messages. The renderer uses the same library as the build plan modal window and excludes error blocks from rendering. The implementation introduced a shared `MarkdownContent` React component and updated relevant frontend components and tests.

## Overview
The goal was to render markdown content in chat blocks instead of displaying plain text. The implementation reused the existing markdown rendering library from the build plan modal and introduced a shared `MarkdownContent` component for consistency across the application.

## Step 1 — Create MarkdownContent Component
**File:** `react/src/components/MarkdownContent.tsx`

A new `MarkdownContent` component was created to handle markdown rendering consistently across different parts of the application. This component parses markdown with `marked` first, then sanitizes the resulting HTML with DOMPurify before injection (sanitizing raw markdown before parsing would let markdown syntax hide HTML). An optional `forbidTags` prop drives a `{ FORBID_TAGS }` DOMPurify config where a call site needs tag exclusions. Trigger words for image or link removal are passed by the caller.

```typescript
import { useMemo } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

export function MarkdownContent({ content }: { content: string; className?: string; forbidTags?: string[] }) {
  const html = useMemo(
    () =>
      DOMPurify.sanitize(
        marked.parse(content, { async: false }) as string,
        forbidTags && forbidTags.length > 0 ? { FORBID_TAGS: forbidTags } : undefined,
      ),
    [content, forbidTags],
  );
  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
```

The `ChatPanel` component was updated to render message bodies through the `MarkdownContent` component. The markdown check lives in a module-local `shouldRenderMarkdown` helper driven by `MARKDOWN_MESSAGE_KINDS`; the failure-details branch (`splitFailureBody`) runs first, so `failure` and `status` messages remain plain text.

```typescript
const MARKDOWN_MESSAGE_KINDS: ChatMessageKind[] = ["message", "plan", "question", "research"];

function shouldRenderMarkdown(message: ChatMessage): boolean {
  return MARKDOWN_MESSAGE_KINDS.includes(message.kind);
}

// inside MessageBubble, after splitting the failure body:
const markdown = shouldRenderMarkdown(message);
```

## Step 3 — Update SessionArtifacts Component
**File:** `react/src/components/SessionArtifacts.tsx`

The `SessionArtifacts` component's build-plan and research modals were changed to reuse the `MarkdownContent` component for rendering their plan/report bodies, ensuring consistent markdown rendering across the application. The research modal passes `forbidTags={['img', 'style']}` to preserve its previous DOMPurify configuration.

## Step 4 — Add CSS Styling
**File:** `react/src/App.css`

CSS styles were added to ensure proper rendering of markdown content in chat blocks, including handling of headings, lists, code blocks, and other markdown elements.

```css
.chat-markdown {
  overflow-wrap: anywhere;
}

.chat-markdown p {
  margin: 0 0 0.5rem;
}

.chat-markdown h1,
.chat-markdown h2,
.chat-markdown h3,
.chat-markdown h4,
.chat-markdown h5,
.chat-markdown h6 {
  margin: 0.75rem 0 0.25rem;
  padding: 0;
  font-size: 0.95rem;
  letter-spacing: 0;
}
```

## Test Results
All frontend tests were updated to account for the new markdown rendering behavior. The changes passed all existing tests, and new tests were added to verify the correct rendering of markdown content in chat blocks.

## Follow-ups
- None

## References
- External: <Linear ticket URL>
- Related: [[2026-06-09-markdown-renderer]]
- Related: [[2026-11-03-ch-2-single-unified-session-view]]
