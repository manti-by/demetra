from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.services.persistence.database import get_session, save_session
from demetra.workflows import setup as workflows_setup


class TestSetupWorkflowHarnessSwitch:
    @pytest.mark.asyncio
    async def test_re_entry_with_changed_harness_resets_session_id_durably(self):
        task_id = "MNT-harness-switch-1"
        await save_session(
            task_id=task_id,
            build_plan="## Implementation Plan\nStep 1: do it.",
            session_id="old-opencode-session",
            harness="opencode",
        )

        with (
            patch.object(
                workflows_setup,
                "search_projects_by_name",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "project-1",
                        "user_id": "user-1",
                        "linear_project_id": None,
                        "name": "test-project",
                        "state": "active",
                        "repository_url": "https://github.com/owner/repo",
                        "repository_name": "repo",
                        "repository_owner": "owner",
                        "local_path": "/tmp/proj",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ],
            ),
            patch.object(
                workflows_setup,
                "get_project_environments",
                new_callable=AsyncMock,
                return_value={"AGENT_HARNESS": "claude"},
            ),
            patch.object(
                workflows_setup,
                "get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(workflows_setup, "setup_project_venv", new_callable=AsyncMock),
            patch.object(workflows_setup, "copy_auth_from_parent", new_callable=AsyncMock),
            patch.object(
                workflows_setup,
                "get_task_by_id",
                new_callable=AsyncMock,
                return_value=MagicMock(
                    id=task_id,
                    slug="mnt-harness-switch-1",
                    full_title=f"{task_id}: Switch harness",
                    title="Switch harness",
                    description="",
                    priority=1,
                    labels=[],
                    created_at="2026-01-01T00:00:00Z",
                ),
            ),
            patch.object(workflows_setup, "git_pull", new_callable=AsyncMock),
            patch.object(
                workflows_setup,
                "git_worktree_create",
                new_callable=AsyncMock,
                return_value=Path("/tmp/worktree"),
            ),
        ):
            context = await workflows_setup.setup_workflow(project_name="test-project", auto_mode=True, task_id=task_id)

        assert context is not None
        assert context.session is not None
        assert context.session.harness == "claude"
        assert context.session.session_id is None

        # Durable: a completely fresh fetch from the DB shows the same reset,
        # not just the in-memory Session object this run mutated.
        persisted = await get_session(task_id=task_id)
        assert persisted is not None
        assert persisted.harness == "claude"
        assert persisted.session_id is None
        assert persisted.build_plan == "## Implementation Plan\nStep 1: do it."

    @pytest.mark.asyncio
    async def test_re_entry_with_unchanged_harness_keeps_session_id(self):
        task_id = "MNT-harness-switch-2"
        await save_session(
            task_id=task_id,
            build_plan="## Implementation Plan\nStep 1: do it.",
            session_id="existing-opencode-session",
            harness="opencode",
        )

        with (
            patch.object(
                workflows_setup,
                "search_projects_by_name",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "project-2",
                        "user_id": "user-1",
                        "linear_project_id": None,
                        "name": "test-project-2",
                        "state": "active",
                        "repository_url": "https://github.com/owner/repo",
                        "repository_name": "repo",
                        "repository_owner": "owner",
                        "local_path": "/tmp/proj2",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ],
            ),
            patch.object(
                workflows_setup,
                "get_project_environments",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                workflows_setup,
                "get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(workflows_setup, "setup_project_venv", new_callable=AsyncMock),
            patch.object(workflows_setup, "copy_auth_from_parent", new_callable=AsyncMock),
            patch.object(
                workflows_setup,
                "get_task_by_id",
                new_callable=AsyncMock,
                return_value=MagicMock(
                    id=task_id,
                    slug="mnt-harness-switch-2",
                    full_title=f"{task_id}: Keep harness",
                    title="Keep harness",
                    description="",
                    priority=1,
                    labels=[],
                    created_at="2026-01-01T00:00:00Z",
                ),
            ),
            patch.object(workflows_setup, "git_pull", new_callable=AsyncMock),
            patch.object(
                workflows_setup,
                "git_worktree_create",
                new_callable=AsyncMock,
                return_value=Path("/tmp/worktree2"),
            ),
        ):
            context = await workflows_setup.setup_workflow(
                project_name="test-project-2", auto_mode=True, task_id=task_id
            )

        assert context is not None
        assert context.session is not None
        assert context.session.harness == "opencode"
        assert context.session.session_id == "existing-opencode-session"
