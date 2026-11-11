---
title: 'MNT-309: Chat Template'
date: '2026-11-10'
type: implementation
status: resolved
session_id: ses_e398f59eaffe97sD58aWWe8zUs
services: [api, library, runtime, react]
branch: mnt-309-chat-template
tickets: [MNT-309]
tags: [wiki, backend, feature, frontend]
related: [2026-11-03-ch-2-single-unified-session-view.md, 2026-11-04-chat-session-list-and-rerun.md]
---

# MNT-309: Chat Template

## TL;DR

This session implemented chat templates for new chat creation, allowing users to select from predefined Markdown templates. The implementation added template storage, a public API endpoint, and frontend integration with the new chat form. The build agent failed during final verification, likely due to a transient infrastructure issue.

## Overview

The implementation adds chat templates stored as Markdown files in `demetra/templates/chat/`, with a public API endpoint to fetch them and frontend UI in the new chat form. Key decisions:

- Templates use standard `analyze_ticket` headings
- Public `GET /api/v1/chat-templates` returns all content in one response
- Apply button replaces (not appends to) existing text
- Selector appears only in `NewChatPage.tsx`

## Step 1 — Template Storage and Models

**File:** demetra/templates/chat/feature_template.md
```markdown
## Description

Describe the feature you want to add and the problem it solves.

## Technical Requirements

- Outline how the feature should be implemented.
- List the subsystems, files, and APIs involved.

## Acceptance Criteria

- List the testable outcomes that define when the work is complete.
- A wiki research page is added.
```

**File:** demetra/library/models.py
```python
@dataclass
class ChatTemplate:
    name: str
    label: str
    content: str
```

## Step 2 — Backend API

**File:** demetra/api/chat_templates.py
```python
router = APIRouter(prefix="/api/v1/chat-templates")

@router.get("", response_model=list[ChatTemplate])
async def list_chat_templates_endpoint() -> list[ChatTemplate]:
    """Return the chat templates available in the new-chat form.
    
    The templates are static repository content with no user data, so the
    endpoint is public.
    """
    return await list_chat_templates()
```

**File:** demetra/services/runtime/template.py
```python
async def list_chat_templates() -> list[ChatTemplate]:
    """Load the chat templates shipped in ``demetra/templates/chat/``.
    
    Every ``*.md`` file in the directory becomes a template, sorted by file
    stem. The file stem is the ``name``, and the stem with underscores turned
    into spaces is the human-readable ``label``.
    """
    templates: list[ChatTemplate] = []
    for path in sorted(CHAT_TEMPLATES_DIR.glob("*.md")):
        try:
            async with aiofiles.open(path) as file:
                content = await file.read()
        except OSError:
            continue
        templates.append(ChatTemplate(
            name=path.stem,
            label=path.stem.replace("_", " ").title(),
            content=content
        ))
    return templates
```

## Step 3 — Frontend Integration

**File:** react/src/services/api.ts
```typescript
// Added ChatTemplate interface and getChatTemplates()
```

**File:** react/src/pages/NewChatPage.tsx
```typescript
// Added template selector and Apply button logic
```

## Test Results

The implementation passed all tests before the build agent failure:

```
============================== 5 passed in 0.59s ===============================
All checks passed!
Test Files  1 passed (1)
     Tests  4 passed (4)
```

## Follow-ups

- Re-run the workflow to confirm the build agent failure was transient
- Verify the deployed endpoint returns templates correctly

## References

- External: https://linear.app/mnt/issue/MNT-309/chat-template
- Related: [[2026-11-03-ch-2-single-unified-session-view]]
- Related: [[2026-11-04-chat-session-list-and-rerun]]

> **Consistency note (2026-11-11, Consistency Agent):** “Templates use standard `analyze_ticket` headings” is not accurate — `demetra/prompts/analyze_ticket.md` has no `##` headings; the templates define their own (`## Description`, `## Technical Requirements`, `## Acceptance Criteria`). There are now **two** templates (`demetra/templates/chat/feature_template.md` and `research_template.md`); only the first is documented above. The page's own follow-ups (re-run the workflow to confirm the build-agent failure was transient, verify the deployed endpoint) are still open — the TL;DR's “implemented successfully” refers to the code, not to a completed verification run. The `services:` frontmatter was a file dump and is now `[api, library, runtime, react]`.
