---
title: 'CH-5: Delete chat button'
date: '2026-11-06'
type: implementation
status: resolved
session_id: ses_e4f736c64ffeYQq2KL14RQEQQL
services: [react]
branch: ch-5-delete-chat-button
tickets: [CH-5]
tags: [wiki, frontend, feature]
related: [2026-11-03-ch-2-single-unified-session-view.md, 2026-11-04-chat-session-list-and-rerun.md]
---

# CH-5: Delete chat button

## TL;DR
This session implemented a delete button for chat sessions, matching the functionality already available for Linear sessions. The changes included adding the button UI, wiring up the delete handler, and adding frontend tests. All tests passed successfully.

## Overview
The implementation added a delete button to the chat session UI that:
1. Appears only when a delete handler is provided
2. Calls the handler with the current task ID when clicked
3. Matches the styling and behavior of the Linear session delete button

## Step 1 — Add Delete Button to ChatPanel
**File:** react/src/components/ChatPanel.tsx:165-177

Added the delete button to the topbar action block:

```tsx
{(onShowLogsToggle || canRerun || onDeleteSession) && (
  <div className="topbar-actions">
    {onDeleteSession && (
      <button
        className="btn-secondary chat-delete-btn"
        onClick={() => onDeleteSession(taskId)}
      >
        Delete
      </button>
    )}
  </div>
)}
```

## Step 2 — Add Frontend Tests
**File:** react/src/components/ChatPanel.test.tsx:80-100

Added tests verifying:
- The delete button only appears when a handler is provided
- Clicking the button calls the handler with the correct task ID

```tsx
it('shows the delete button only when a handler is provided', async () => {
  vi.mocked(getChat).mockResolvedValue(makeDetail());

  const { rerender } = render(<ChatPanel taskId="CH-1" />);
  await waitFor(() => {
    expect(screen.getByText('CH-1: Add authentication')).toBeInTheDocument();
  });
  expect(screen.queryByText('Delete')).not.toBeInTheDocument();

  rerender(<ChatPanel taskId="CH-1" onDeleteSession={vi.fn()} />);
  expect(screen.getByText('Delete')).toBeInTheDocument();
});

it('deletes the session with its task id', async () => {
  vi.mocked(getChat).mockResolvedValue(makeDetail());
  const onDeleteSession = vi.fn();

  render(<ChatPanel taskId="CH-1" onDeleteSession={onDeleteSession} />);

  fireEvent.click(await screen.findByText('Delete'));

  expect(onDeleteSession).toHaveBeenCalledWith('CH-1');
});
```

## Step 3 — Update ChatPage with Real Delete Handler
**File:** react/src/pages/ChatPage.tsx

Replaced the stub delete handler with one that:
1. Calls `deleteSession(taskId)` 
2. Navigates to the home page on success
3. Shows an error message on failure

## Test Results
All 1203 tests passed successfully, including the new frontend tests for the delete button functionality.

## Follow-ups
- None

## References
- External: <linear ticket URL>
- Related: [[2026-11-03-ch-2-single-unified-session-view]]
- Related: [[2026-11-04-chat-session-list-and-rerun]]
