from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import BuildError
from demetra.library.models import Session, SessionEnvironment
from demetra.workflows.rebase import run_rebase_workflow


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
        patch("demetra.workflows.rebase.get_session", new_callable=AsyncMock) as mock_get_session,
        patch("demetra.workflows.rebase.setup_session_logging", new_callable=AsyncMock),
        patch("demetra.workflows.rebase.get_project_by_id_system", new_callable=AsyncMock) as mock_get_project,
        patch("demetra.workflows.rebase.get_project_environments", new_callable=AsyncMock) as mock_get_env,
        patch("demetra.workflows.rebase.get_user_environments_decrypted", new_callable=AsyncMock) as mock_get_user_env,
        patch("demetra.workflows.rebase.setup_project_venv", new_callable=AsyncMock) as mock_venv,
        patch("demetra.workflows.rebase.git_fetch", new_callable=AsyncMock) as mock_fetch,
        patch("demetra.workflows.rebase.git_worktree_create", new_callable=AsyncMock) as mock_wt_create,
        patch("demetra.workflows.rebase.git_worktree_remove", new_callable=AsyncMock) as mock_wt_remove,
        patch("demetra.workflows.rebase.get_pr_info", new_callable=AsyncMock) as mock_pr_info,
        patch("demetra.workflows.rebase.perform_git_rebase", new_callable=AsyncMock) as mock_perform_rebase,
        patch("demetra.workflows.rebase.write_session_wiki_page", new_callable=AsyncMock) as mock_write_page,
        patch("demetra.workflows.rebase.resolve_task_by_id", new_callable=AsyncMock) as mock_get_task,
        patch("demetra.workflows.rebase.run_ci_loop", new_callable=AsyncMock) as mock_ci_loop,
        patch("demetra.workflows.rebase.update_session_step", new_callable=AsyncMock) as mock_update_step,
    ):
        mock_get_session.return_value = SESSION
        mock_get_project.return_value = PROJECT_DATA
        mock_get_env.return_value = {}
        mock_get_user_env.return_value = {}
        mock_wt_create.return_value = Path("/worktree/owner/repo/feature-branch")
        mock_get_task.return_value = None
        mock_ci_loop.return_value = True
        yield {
            "mock_get_session": mock_get_session,
            "mock_get_project": mock_get_project,
            "mock_get_env": mock_get_env,
            "mock_get_user_env": mock_get_user_env,
            "mock_venv": mock_venv,
            "mock_fetch": mock_fetch,
            "mock_wt_create": mock_wt_create,
            "mock_wt_remove": mock_wt_remove,
            "mock_pr_info": mock_pr_info,
            "mock_perform_rebase": mock_perform_rebase,
            "mock_write_page": mock_write_page,
            "mock_get_task": mock_get_task,
            "mock_ci_loop": mock_ci_loop,
            "mock_update_step": mock_update_step,
        }


class TestRunRebaseWorkflow:
    @pytest.mark.asyncio
    async def test_rebase_succeeds(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = ("feature/branch", "main")
        base_mocks["mock_perform_rebase"].return_value = True

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        base_mocks["mock_fetch"].assert_awaited_once()
        base_mocks["mock_wt_create"].assert_awaited_once()
        base_mocks["mock_perform_rebase"].assert_awaited_once()
        base_mocks["mock_wt_remove"].assert_awaited_once()
        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "completed",
        ]
        base_mocks["mock_ci_loop"].assert_awaited_once()
        call = base_mocks["mock_ci_loop"].await_args.kwargs
        assert call["task_id"] == "TASK-123"
        assert call["project_id"] == "proj-1"
        assert call["branch_name"] == "feature/branch"
        assert call["task_title"] == "owner/repo #42 - rebase"
        assert call["session_id"] is None
        assert isinstance(call["environment"], SessionEnvironment)

    @pytest.mark.asyncio
    async def test_rebase_returns_ci_failure_after_wiki_page_write(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = ("feature/branch", "main")
        base_mocks["mock_perform_rebase"].return_value = True
        base_mocks["mock_ci_loop"].return_value = False
        base_mocks["mock_get_task"].return_value = "task"

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False
        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "failed",
        ]
        base_mocks["mock_write_page"].assert_awaited_once()
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rebase_ci_agent_failure_returns_false(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = ("feature/branch", "main")
        base_mocks["mock_perform_rebase"].return_value = True
        base_mocks["mock_ci_loop"].side_effect = BuildError("build agent failed")

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False
        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "failed",
        ]
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rebase_failure_pr_info_error(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = None

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=999,
            full_name="owner/repo",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_rebase_failure_session_not_found(self):
        with (
            patch("demetra.workflows.rebase.get_session", new_callable=AsyncMock) as mock_get_session,
            patch("demetra.workflows.rebase.setup_session_logging", new_callable=AsyncMock),
        ):
            mock_get_session.return_value = None

            result = await run_rebase_workflow(
                task_id="TASK-UNKNOWN",
                project_id="proj-1",
                pr_number=42,
                full_name="owner/repo",
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_rebase_failure_project_not_found(self, base_mocks):
        base_mocks["mock_get_project"].return_value = None

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-missing",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False
        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "failed",
        ]

    @pytest.mark.asyncio
    async def test_project_lookup_failure_persists_failed_step(self, base_mocks):
        base_mocks["mock_get_project"].side_effect = RuntimeError("database down")

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False
        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "failed",
        ]
        base_mocks["mock_wt_remove"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_project_setup_failure_persists_failed_step_before_raising(self, base_mocks):
        base_mocks["mock_get_env"].side_effect = ValueError("bad environment")

        with pytest.raises(ValueError, match="bad environment"):
            await run_rebase_workflow(
                task_id="TASK-123",
                project_id="proj-1",
                pr_number=42,
                full_name="owner/repo",
            )

        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "failed",
        ]

    @pytest.mark.asyncio
    async def test_rebase_perform_rebase_fails(self, base_mocks):
        base_mocks["mock_pr_info"].return_value = ("feature/branch", "main")
        base_mocks["mock_perform_rebase"].return_value = False

        result = await run_rebase_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is False
        assert [call.kwargs["step"] for call in base_mocks["mock_update_step"].await_args_list] == [
            "build",
            "failed",
        ]
        base_mocks["mock_wt_remove"].assert_awaited_once()
