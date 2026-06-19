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
        patch("demetra.workflows.merge.git_force_push", new_callable=AsyncMock) as mock_push,
        patch("demetra.workflows.merge.git_add_all", new_callable=AsyncMock) as mock_add_all,
        patch("demetra.workflows.merge.git_worktree_remove", new_callable=AsyncMock) as mock_wt_remove,
        patch("demetra.workflows.merge.run_command", new_callable=AsyncMock) as mock_run,
    ):
        mock_get_session.return_value = SESSION
        mock_get_project.return_value = PROJECT_DATA
        mock_get_env.return_value = {}
        mock_wt_create.return_value = Path("/worktree/owner/repo/feature-branch")
        yield {
            "mock_get_session": mock_get_session,
            "mock_get_project": mock_get_project,
            "mock_get_env": mock_get_env,
            "mock_fetch": mock_fetch,
            "mock_add_all": mock_add_all,
            "mock_wt_create": mock_wt_create,
            "mock_push": mock_push,
            "mock_wt_remove": mock_wt_remove,
            "mock_run": mock_run,
        }


class TestRunMergeWorkflow:
    @pytest.mark.asyncio
    async def test_merge_succeeds_on_first_try(self, base_mocks):
        mock_run = base_mocks["mock_run"]
        mock_run.side_effect = [
            (0, '{"headRefName": "feature/branch", "baseRefName": "main"}', ""),  # gh pr view
            (0, "", ""),  # git merge succeeds
        ]

        result = await run_merge_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        base_mocks["mock_fetch"].assert_awaited_once()
        base_mocks["mock_wt_create"].assert_awaited_once()
        base_mocks["mock_push"].assert_awaited_once()
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_failure_pr_info_error(self, base_mocks):
        mock_run = base_mocks["mock_run"]
        mock_run.return_value = (1, "", "PR not found")

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
    async def test_merge_conflict_agent_resolves(self, base_mocks):
        mock_run = base_mocks["mock_run"]
        mock_run.side_effect = [
            (0, '{"headRefName": "feature/branch", "baseRefName": "main"}', ""),  # gh pr view
            (1, "", "CONFLICT (content): Merge conflict in file.txt"),  # git merge fails
            (0, "file.txt\n", ""),  # loop attempt 1 diff - has conflicts
            (0, "", ""),  # loop attempt 2 diff - no conflicts, agent resolved -> break
            (0, "", ""),  # remaining check after loop
            (0, "", ""),  # git commit --no-edit
        ]

        with patch("demetra.workflows.merge.opencode_merge_agent", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = (0, "Resolved conflicts", "")

            with patch("demetra.workflows.merge.get_prompt", new_callable=AsyncMock) as mock_prompt:
                mock_prompt.return_value = "Resolve conflicts task"

                result = await run_merge_workflow(
                    task_id="TASK-123",
                    project_id="proj-1",
                    pr_number=42,
                    full_name="owner/repo",
                )

        assert result is True
        base_mocks["mock_fetch"].assert_awaited_once()
        base_mocks["mock_wt_create"].assert_awaited_once()
        mock_agent.assert_awaited_once()
        mock_prompt.assert_awaited_once_with(
            "merge_agent",
            conflicted_files="- file.txt",
            merge_error="CONFLICT (content): Merge conflict in file.txt",
        )
        base_mocks["mock_push"].assert_awaited_once()
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_conflict_agent_fails(self, base_mocks):
        mock_run = base_mocks["mock_run"]
        mock_run.side_effect = [
            (0, '{"headRefName": "feature/branch", "baseRefName": "main"}', ""),  # gh pr view
            (1, "", "CONFLICT (content): Merge conflict in file.txt"),  # git merge fails
            (0, "file.txt\n", ""),  # diff --name-only --diff-filter=U
        ]

        with (
            patch("demetra.workflows.merge.opencode_merge_agent", new_callable=AsyncMock) as mock_agent,
            patch("demetra.workflows.merge.get_prompt", new_callable=AsyncMock) as mock_prompt,
        ):
            mock_prompt.return_value = "Resolve conflicts task"
            mock_agent.return_value = (1, "", "Agent could not resolve")

            result = await run_merge_workflow(
                task_id="TASK-123",
                project_id="proj-1",
                pr_number=42,
                full_name="owner/repo",
            )

        assert result is False
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_conflict_loop_exhausted(self, base_mocks):
        mock_run = base_mocks["mock_run"]
        mock_run.side_effect = [
            (0, '{"headRefName": "feature/branch", "baseRefName": "main"}', ""),  # gh pr view
            (1, "", "CONFLICT (content): Merge conflict in file.txt"),  # git merge fails
            (0, "file.txt\n", ""),  # diff attempt 1 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 2 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 3 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 4 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 5 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 6 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 7 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 8 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 9 - still conflicted
            (0, "file.txt\n", ""),  # diff attempt 10 - still conflicted
            (0, "file.txt\n", ""),  # remaining check after loop
        ]

        with (
            patch("demetra.workflows.merge.opencode_merge_agent", new_callable=AsyncMock) as mock_agent,
            patch("demetra.workflows.merge.get_prompt", new_callable=AsyncMock) as mock_prompt,
        ):
            mock_prompt.return_value = "Resolve conflicts task"
            mock_agent.return_value = (0, "Attempted", "")

            result = await run_merge_workflow(
                task_id="TASK-123",
                project_id="proj-1",
                pr_number=42,
                full_name="owner/repo",
            )

        assert result is False
        assert mock_agent.await_count == 10
        assert mock_prompt.await_count == 10
        base_mocks["mock_wt_remove"].assert_awaited_once()
