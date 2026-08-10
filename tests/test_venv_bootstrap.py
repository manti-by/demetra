from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.models import Project
from demetra.services.runtime.project import setup_project_venv


def _make_project(local_path: Path) -> Project:
    return Project(
        id="project-1",
        user_id="user-1",
        linear_project_id=None,
        name="test-project",
        state="active",
        repository_url="https://github.com/owner/repo",
        repository_name="repo",
        repository_owner="owner",
        local_path=local_path,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class TestSetupProjectVenv:
    @pytest.mark.asyncio
    async def test_creates_venv_on_first_use(self, tmp_path: Path):
        project = _make_project(local_path=tmp_path)

        with patch(
            "demetra.services.runtime.project.run_command",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ) as mock_run:
            venv_path = await setup_project_venv(project=project)

        assert venv_path == tmp_path / ".venv"
        assert mock_run.await_count == 1
        call = mock_run.await_args
        assert call is not None
        command = call.kwargs["command"]
        assert command[1:3] == ["venv", "--seed"]
        assert command[-1] == str(tmp_path / ".venv")
        assert call.kwargs["project_id"] == "project-1"
        assert project.environment["VIRTUAL_ENV"] == str(tmp_path / ".venv")
        assert project.environment["UV_PROJECT_ENVIRONMENT"] == str(tmp_path / ".venv")

    @pytest.mark.asyncio
    async def test_reuses_existing_venv(self, tmp_path: Path):
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        project = _make_project(local_path=tmp_path)

        with patch(
            "demetra.services.runtime.project.run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            venv_path = await setup_project_venv(project=project)

        assert venv_path == venv_dir
        mock_run.assert_not_awaited()
        assert project.environment["VIRTUAL_ENV"] == str(venv_dir)

    @pytest.mark.asyncio
    async def test_raises_when_bootstrap_fails_and_removes_partial_venv(self, tmp_path: Path):
        project = _make_project(local_path=tmp_path)

        async def failing_uv_venv(**kwargs):
            # Simulate uv creating a partial .venv before failing.
            (tmp_path / ".venv" / "bin").mkdir(parents=True)
            return (1, "", "boom")

        with patch(
            "demetra.services.runtime.project.run_command",
            new_callable=AsyncMock,
            side_effect=failing_uv_venv,
        ):
            with pytest.raises(RuntimeError, match="Failed to create UV venv"):
                await setup_project_venv(project=project)

        # The partial venv must be removed so the next run retries bootstrap.
        assert not (tmp_path / ".venv").exists()

    @pytest.mark.asyncio
    async def test_raises_when_local_path_missing(self):
        project = _make_project(local_path=Path("/nonexistent"))
        project = replace(project, local_path=None)  # type: ignore[arg-type]

        with pytest.raises(RuntimeError, match="local path"):
            await setup_project_venv(project=project)

    def test_uv_setting_used(self, tmp_path: Path):
        from demetra.settings import UV

        assert "path" in UV
        assert UV["path"] is not None


class TestSetupWorkflowVenvWiring:
    @pytest.mark.asyncio
    async def test_setup_workflow_merges_user_env_under_project_env(self):
        from demetra.workflows import setup as setup_module

        with (
            patch.object(
                setup_module,
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
                setup_module,
                "get_project_environments",
                new_callable=AsyncMock,
                return_value={"CONFLICT_KEY": "project-value", "PROJECT_ONLY": "p"},
            ),
            patch.object(
                setup_module,
                "get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"CONFLICT_KEY": "user-value", "USER_ONLY": "u"},
            ),
            patch.object(
                setup_module,
                "setup_project_venv",
                new_callable=AsyncMock,
            ),
            patch.object(
                setup_module,
                "copy_auth_from_parent",
                new_callable=AsyncMock,
            ),
            patch.object(
                setup_module,
                "get_linear_task",
                new_callable=AsyncMock,
                return_value=MagicMock(
                    id="MNT-1",
                    slug="mnt-1-fix",
                    full_title="MNT-1: Fix",
                    title="Fix",
                    description="",
                    priority=1,
                    created_at="2026-01-01T00:00:00Z",
                ),
            ),
            patch.object(
                setup_module,
                "get_session",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                setup_module,
                "git_pull",
                new_callable=AsyncMock,
            ),
            patch.object(
                setup_module,
                "git_worktree_create",
                new_callable=AsyncMock,
                return_value=Path("/tmp/worktree"),
            ),
        ):
            context = await setup_module.setup_workflow(project_name="test-project", auto_mode=True)

        assert context is not None
        assert context.project.environment["CONFLICT_KEY"] == "project-value"
        assert context.project.environment["PROJECT_ONLY"] == "p"
        assert context.project.environment["USER_ONLY"] == "u"
        assert context.project.user_environment["CONFLICT_KEY"] == "user-value"
