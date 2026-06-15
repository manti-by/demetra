from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.models import Context, LinearTask, Project
from demetra.services.git import (
    git_add_all,
    git_branch_delete,
    git_cleanup,
    git_commit,
    git_push,
    git_worktree_create,
    git_worktree_remove,
)


def _make_project(faker) -> Project:
    return Project(
        id=str(uuid4()),
        user_id=str(uuid4()),
        linear_project_id=str(uuid4()),
        name="demetra",
        state="active",
        repository_url="https://github.com/test/demetra",
        repository_name="demetra",
        repository_owner="test",
        local_path=Path(f"/tmp/{faker.slug()}"),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )


def _make_context(faker) -> Context:
    return Context(
        project=_make_project(faker),
        auto_mode=False,
        linear_task=LinearTask(
            id=str(uuid4()),
            identifier="MNT-123",
            title=faker.sentence(),
            description=faker.text(),
            priority="1",
            created_at=datetime.now().isoformat(),
            comments=[],
        ),
        branch_name="feature/test",
        worktree_path=Path(f"/tmp/{faker.slug()}"),
        session=None,
    )


class TestGitService:
    @pytest.fixture
    def mock_run_command(self):
        with patch("demetra.services.git.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (0, "", "")
            yield mock

    @pytest.fixture
    def mock_git_worktree_remove(self):
        with patch("demetra.services.git.git_worktree_remove", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_git_branch_delete(self):
        with patch("demetra.services.git.git_branch_delete", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_git_add_all(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_run_command.return_value = (0, "file1.py\nfile2.py\n", "")
        result = await git_add_all(target_path)
        assert result is True

    @pytest.mark.asyncio
    async def test_git_add_all_no_files(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        result = await git_add_all(target_path)
        assert result is False

    @pytest.mark.asyncio
    async def test_git_commit(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        message = faker.sentence()
        await git_commit(target_path, message)

    @pytest.mark.asyncio
    async def test_git_push(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        branch_name = f"feature/{faker.slug()}"
        await git_push(target_path, branch_name)

    @pytest.mark.asyncio
    async def test_git_branch_delete(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        branch_name = f"feature/{faker.slug()}"
        await git_branch_delete(target_path, branch_name)

    @pytest.mark.asyncio
    async def test_git_worktree_remove(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        worktree_path = Path(f"/tmp/worktree/{faker.slug()}")
        await git_worktree_remove(target_path, worktree_path)

    @pytest.mark.asyncio
    async def test_git_worktree_remove_failure_raises(self, faker, mock_run_command):
        target_path = Path(f"/tmp/{faker.slug()}")
        worktree_path = Path(f"/tmp/worktree/{faker.slug()}")
        mock_run_command.return_value = (1, "", "fatal: not a working tree")
        with pytest.raises(RuntimeError, match="Failed to remove worktree"):
            await git_worktree_remove(target_path, worktree_path)

    @pytest.mark.asyncio
    async def test_git_worktree_create(self, faker, mock_run_command, mock_git_worktree_remove, mock_git_branch_delete):
        project = _make_project(faker)
        branch_name = f"feature/{faker.slug()}"
        result = await git_worktree_create(project=project, branch_name=branch_name)

        assert result is not None
        assert project.repository_owner in str(result)
        assert project.repository_name in str(result)
        assert branch_name in str(result)

    @pytest.mark.asyncio
    async def test_git_worktree_create_failure_raises(
        self, faker, mock_run_command, mock_git_worktree_remove, mock_git_branch_delete
    ):
        project = _make_project(faker)
        branch_name = f"feature/{faker.slug()}"
        mock_run_command.return_value = (128, "", "fatal: invalid reference")
        with pytest.raises(RuntimeError, match="Failed to create worktree"):
            await git_worktree_create(project=project, branch_name=branch_name)

    @pytest.mark.asyncio
    async def test_git_cleanup_success(self, faker, mock_git_worktree_remove):
        context = _make_context(faker)
        await git_cleanup(context, is_success=True)

    @pytest.mark.asyncio
    async def test_git_cleanup_failure_deletes_branch(self, faker, mock_git_worktree_remove, mock_git_branch_delete):
        context = _make_context(faker)
        await git_cleanup(context, is_success=False)
