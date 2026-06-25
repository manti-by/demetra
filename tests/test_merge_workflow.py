from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.models import Session
from demetra.workflows.merge import run_merge_workflow


PROJECT_DATA = {
    "id": "proj-1",
    "user_id": "user-1",
    "linear_project_id": "linear-1",
    "name": "test-project",
    "repository_url": "https://github.com/owner/repo.git",
    "repository_name": "repo",
    "repository_owner": "owner",
    "local_path": "/tmp/test-project",
    "state": "active",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

SESSION = Session(
    task_id="TASK-123",
    build_plan="plan",
    posted_to_linear=True,
    created_at="2026-01-01T00:00:00Z",
    updated_at="2026-01-01T00:00:00Z",
    project_id="proj-1",
    user_id="user-1",
    pr_link="https://github.com/owner/repo/pull/42",
)


@pytest.fixture
def base_mocks():
    with (
        patch("demetra.workflows.merge.get_session", new_callable=AsyncMock) as mock_get_session,
        patch("demetra.workflows.merge.setup_session_logging", new_callable=AsyncMock),
        patch("demetra.workflows.merge.get_project_by_id_system", new_callable=AsyncMock) as mock_get_project,
        patch("demetra.workflows.merge.get_project_environments", new_callable=AsyncMock) as mock_get_env,
        patch("demetra.workflows.merge.git_fetch", new_callable=AsyncMock) as mock_fetch,
        patch("demetra.workflows.merge.git_worktree_create", new_callable=AsyncMock) as mock_wt_create,
        patch("demetra.workflows.merge.git_worktree_remove", new_callable=AsyncMock) as mock_wt_remove,
        patch("demetra.workflows.merge.get_pr_info", new_callable=AsyncMock) as mock_pr_info,
        patch("demetra.workflows.merge.perform_git_merge", new_callable=AsyncMock) as mock_perform_merge,
    ):
        mock_get_session.return_value = SESSION
        mock_get_project.return_value = PROJECT_DATA
        mock_get_env.return_value = {}
        mock_fetch.return_value = None
        mock_wt_create.return_value = Path("/worktree/owner/repo/feature-branch")
        yield {
            "mock_get_session": mock_get_session,
            "mock_get_project": mock_get_project,
            "mock_get_env": mock_get_env,
            "mock_fetch": mock_fetch,
            "mock_wt_create": mock_wt_create,
            "mock_wt_remove": mock_wt_remove,
            "mock_pr_info": mock_pr_info,
            "mock_perform_merge": mock_perform_merge,
        }


class TestRunMergeWorkflow:
    @pytest.mark.asyncio
    async def test_merge_succeeds(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = ("feature/branch", "main")
        base_mocks["mock_perform_merge"].return_value = True

        result = await run_merge_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        base_mocks["mock_fetch"].assert_awaited_once()
        base_mocks["mock_wt_create"].assert_awaited_once()
        base_mocks["mock_perform_merge"].assert_awaited_once()
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_failure_pr_info_error(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = None

        result = await run_merge_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=999,
            full_name="owner/repo",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_merge_failure_session_not_found(self):
        with (
            patch("demetra.workflows.merge.get_session", new_callable=AsyncMock) as mock_get_session,
            patch("demetra.workflows.merge.setup_session_logging", new_callable=AsyncMock),
        ):
            mock_get_session.return_value = None

            result = await run_merge_workflow(
                task_id="TASK-UNKNOWN",
                project_id="proj-1",
                pr_number=42,
                full_name="owner/repo",
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_merge_failure_project_not_found(self, base_mocks):
        base_mocks["mock_get_project"].return_value = None

        result = await run_merge_workflow(
            task_id="TASK-123",
            project_id="proj-missing",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_merge_perform_merge_fails(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = ("feature/branch", "main")
        base_mocks["mock_perform_merge"].return_value = False

        result = await run_merge_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False
        base_mocks["mock_wt_remove"].assert_awaited_once()
