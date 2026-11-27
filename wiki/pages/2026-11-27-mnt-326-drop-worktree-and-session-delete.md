---
title: 'MNT-326: Drop worktree and a session delete'
generated: {by: demetra, at: '2026-11-27T00:00:00Z'}
description: The `delete_session` service in the persistence subsystem was updated to remove associated worktrees using `git_worktree_remove` with `force=True`, and tests were added to verify this behavior, all of which passed successfully.
type: implementation
status: stable
session_id: ses_de34740b1ffeUTbxqZMCRsUtwZ
services: [persistence/database, pyproject, test_database, uv, .sessions, INDEX, 2026-11-27-mnt-326-drop-worktree-and-session-delete]
branch: mnt-326-drop-worktree-and-a-session-delete
tickets: [MNT-326]
tags: [wiki, bug, backend]
related: [2026-11-19-ch-15-worktree-management.md, 2026-11-06-ch-5-delete-chat-button.md, 2026-11-04-chat-session-list-and-rerun.md]
---

# MNT-326: Drop worktree and a session delete

## TL;DR

This session implemented worktree removal when deleting a session. The `delete_session` service was updated to remove the associated worktree using `git_worktree_remove` with `force=True`. Tests were added to verify worktree removal behavior. All tests passed successfully.

## Overview

The goal was to ensure that when a session is deleted, its associated worktree is also removed if it exists. This involved modifying the `delete_session` service in `demetra/services/persistence/database.py` to include worktree removal logic and adding corresponding tests.

## Step 1 — Add worktree removal to delete_session

**File:** demetra/services/persistence/database.py

A new private helper `_remove_session_worktree` was added to handle worktree removal:

```python
async def _remove_session_worktree(project: Project, branch_name: str) -> None:
    """Force-remove the worktree a session used, when one is still present."""
    from demetra.services.vcs.git import get_worktree_path, git_worktree_exists, git_worktree_remove

    if not git_worktree_exists(project=project, branch_name=branch_name):
        return

    await git_worktree_remove(
        target_path=project.local_path,
        worktree_path=get_worktree_path(project=project, branch_name=branch_name),
        force=True,
        project_id=project.id,
    )
```

This helper is called from `delete_session` after committing the database transaction:

```python
if task is not None and project_row is not None and project_row.get("local_path"):
    project = Project(**project_row)
    project.local_path = Path(project.local_path)
    try:
        await _remove_session_worktree(project=project, branch_name=task.slug)
    except (OSError, RuntimeError):
        logger.warning(f"Failed to remove worktree for deleted session {task_id}")
```

## Step 2 — Add tests for worktree removal

**File:** tests/test_database.py

A new `TestDeleteSessionWorktree` class was added with test cases covering:

- Removing an existing worktree with `force=True`
- No removal call when no worktree exists
- Successful deletion even if removal fails with `RuntimeError`

```python
class TestDeleteSessionWorktree:
    @pytest.mark.asyncio
    async def test_removes_existing_worktree_with_force(self, tmp_path: Path):
        # Setup test data
        with (
            patch("demetra.services.vcs.git.git_worktree_exists", return_value=True) as mock_exists,
            patch("demetra.services.vcs.git.get_worktree_path", return_value=worktree_path) as mock_path,
            patch("demetra.services.vcs.git.git_worktree_remove", new_callable=AsyncMock) as mock_remove,
        ):
            assert await delete_session(task_id=task_id, user_id=user_id) is True
            mock_remove.assert_called_once_with(
                target_path=project["local_path"],
                worktree_path=worktree_path,
                force=True,
                project_id=project["id"],
            )
```

## Test Results

All tests passed successfully, including the new worktree removal tests:

```
1834 passed in 43.31s
```

## Follow-ups

- None

## References
- External: https://linear.app/mnt/issue/MNT-326/drop-worktree-and-a-session-delete
- Related: [2026-11-19-ch-15-worktree-management](/pages/2026-11-19-ch-15-worktree-management.md)
- Related: [2026-11-06-ch-5-delete-chat-button](/pages/2026-11-06-ch-5-delete-chat-button.md)
- Related: [2026-11-04-chat-session-list-and-rerun](/pages/2026-11-04-chat-session-list-and-rerun.md)
