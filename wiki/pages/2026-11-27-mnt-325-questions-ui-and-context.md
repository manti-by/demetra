---
title: 'MNT-325: Questions UI and context'
generated: {by: demetra, at: '2026-11-27T00:00:00Z'}
description: The chat UI was updated to support independent question-answer pairs, enabling users to answer each plan agent question separately, with database storage linking answers to questions and a new API endpoint for submitting answers without triggering workflow reruns.
type: implementation
status: stable
session_id: ses_de3a004c4ffe5PVA57PM5JA3xu
services: [api, library, agents/opencode, chat/__init__, chat/tasks, persistence/database, workflows, d5e6f7a8b9c0_add_messages_answer_link, pyproject, App, ChatPanel.test, ChatPanel, ChatPage.test, test_chat_tasks, test_chats, test_opencode, test_workflows, uv, INDEX, 2026-11-27-mnt-325-questions-ui-and-context]
branch: mnt-325-questions-ui-and-context
tickets: [MNT-325]
tags: [wiki, feature, frontend, backend]
related: [2026-11-04-chat-session-list-and-rerun.md, 2026-11-03-ch-2-single-unified-session-view.md, 2026-11-12-ch-11-failed-status-for-awaiting-input-tickets.md]
---

# MNT-325: Questions UI and context

## TL;DR

Implemented independent question-answer pairs in the chat UI, allowing users to answer each plan agent question separately. Added database support for linking answers to questions and a new API endpoint for submitting answers without triggering workflow reruns. The system now compiles Q&A pairs in order when the workflow is explicitly rerun.

## Overview

The changes enable:
1. UI to answer each question individually with inline inputs
2. Database storage of answers linked to their questions
3. Explicit workflow rerun to compile all answers
4. Preservation of question-answer order

## Step 1 — Schema Updates

**File:** demetra/library/tables.py:62,68,74,83

Added database columns to link answers to questions and track context inclusion:
```python
Column("related_id", String(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=True),
Column("is_added_to_context", Boolean(), nullable=False, server_default="false"),
Index("ix_messages_related_id", "related_id"),
"kind IN ('message', 'question', 'answer', 'plan', 'failure', 'research', 'status', 'comment')",
```

## Step 2 — Model Updates

**File:** demetra/library/models.py:36,61,66,194-198

Extended models to support answer messages and their relationships:
```python
ChatMessageKind = Literal["message", "question", "answer", "plan", "failure", "research", "status", "comment"]

class Message:
    related_id: str | None = None
    is_added_to_context: bool = False

@dataclass
class CreateChatAnswer:
    body: str
```

## Step 3 — API Endpoint

**File:** demetra/api/chats.py:312-359

Added new endpoint for submitting answers without workflow rerun:
```python
@router.post("/{task_id}/questions/{question_id}/answer", response_model=dict, status_code=201)
async def create_chat_answer_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    question_id: str,
    request: CreateChatAnswer,
    user: UserResponse = Depends(get_current_user_dep),
) -> dict:
    """Answer one plan question without starting a workflow run."""
    chat = await get_chat(task_id=task_id, user_id=user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Answer cannot be empty")

    message = await post_chat_answer(
        task_id=task_id,
        question_id=question_id,
        body=body,
        author_id=user.id,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return {"message": message}
```

## Step 4 — Workflow Integration

**File:** demetra/workflows/plan.py

Modified plan workflow to:
1. Accept existing session_id to continue conversations
2. Compile answers in original question order
3. Mark answers as added to context

## Test Results

All 1844 tests passed, including new tests for:
- Question-answer pair compilation
- Workflow continuation with existing session
- Answer submission without workflow rerun
- Context preservation during reruns

## Follow-ups

- None

## References
- External: https://linear.app/mnt/issue/MNT-325/questions-ui-and-context
- Related: [2026-11-04-chat-session-list-and-rerun](/pages/2026-11-04-chat-session-list-and-rerun.md)
- Related: [2026-11-03-ch-2-single-unified-session-view](/pages/2026-11-03-ch-2-single-unified-session-view.md)
- Related: [2026-11-12-ch-11-failed-status-for-awaiting-input-tickets](/pages/2026-11-12-ch-11-failed-status-for-awaiting-input-tickets.md)
