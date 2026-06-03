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


class TestGitService:
    @pytest.mark.asyncio
    async def test_git_add_all(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
            return_value=(0, "file1.py\nfile2.py\n", ""),
        ):
            await git_add_all(target_path)

    @pytest.mark.asyncio
    async def test_git_add_all_no_files(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ):
            with pytest.raises(RuntimeError, match="No files to commit"):
                await git_add_all(target_path)

    @pytest.mark.asyncio
    async def test_git_commit(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        message = faker.sentence()

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
        ):
            await git_commit(target_path, message)

    @pytest.mark.asyncio
    async def test_git_push(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        branch_name = f"feature/{faker.slug()}"

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
        ):
            await git_push(target_path, branch_name)

    @pytest.mark.asyncio
    async def test_git_branch_delete(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        branch_name = f"feature/{faker.slug()}"

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
        ):
            await git_branch_delete(target_path, branch_name)

    @pytest.mark.asyncio
    async def test_git_worktree_remove(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        worktree_path = Path(f"/tmp/worktree/{faker.slug()}")

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ):
            await git_worktree_remove(target_path, worktree_path)

    @pytest.mark.asyncio
    async def test_git_worktree_remove_failure_raises(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        worktree_path = Path(f"/tmp/worktree/{faker.slug()}")

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
            return_value=(1, "", "fatal: not a working tree"),
        ):
            with pytest.raises(RuntimeError, match="Failed to remove worktree"):
                await git_worktree_remove(target_path, worktree_path)

    @pytest.mark.asyncio
    async def test_git_worktree_create(self, faker):
        project = Project(
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
        branch_name = f"feature/{faker.slug()}"

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ):
            with patch(
                "demetra.services.git.git_worktree_remove",
                new_callable=AsyncMock,
            ):
                with patch(
                    "demetra.services.git.git_branch_delete",
                    new_callable=AsyncMock,
                ):
                    result = await git_worktree_create(project=project, branch_name=branch_name)

        assert result is not None
        assert project.repository_owner in str(result)
        assert project.repository_name in str(result)
        assert branch_name in str(result)

    @pytest.mark.asyncio
    async def test_git_worktree_create_failure_raises(self, faker):
        project = Project(
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
        branch_name = f"feature/{faker.slug()}"

        with patch(
            "demetra.services.git.run_command",
            new_callable=AsyncMock,
            return_value=(128, "", "fatal: invalid reference"),
        ):
            with patch(
                "demetra.services.git.git_worktree_remove",
                new_callable=AsyncMock,
            ):
                with patch(
                    "demetra.services.git.git_branch_delete",
                    new_callable=AsyncMock,
                ):
                    with pytest.raises(RuntimeError, match="Failed to create worktree"):
                        await git_worktree_create(project=project, branch_name=branch_name)

    @pytest.mark.asyncio
    async def test_git_cleanup_success(self, faker):
        context = Context(
            project=Project(
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
            ),
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

        with patch(
            "demetra.services.git.git_worktree_remove",
            new_callable=AsyncMock,
        ):
            await git_cleanup(context, is_success=True)

    @pytest.mark.asyncio
    async def test_git_cleanup_failure_deletes_branch(self, faker):
        from datetime import datetime
        from uuid import uuid4

        context = Context(
            project=Project(
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
            ),
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

        with patch(
            "demetra.services.git.git_worktree_remove",
            new_callable=AsyncMock,
        ):
            with patch(
                "demetra.services.git.git_branch_delete",
                new_callable=AsyncMock,
            ):
                await git_cleanup(context, is_success=False)
