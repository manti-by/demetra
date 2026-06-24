from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.rebase import perform_git_rebase


WORKTREE_PATH = Path("/tmp/worktree/feature-branch")
ENV = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com"}


class TestPerformGitRebase:
    @pytest.fixture
    def mock_run_command(self):
        with patch("demetra.services.rebase.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (0, "", "")
            yield mock

    @pytest.fixture
    def mock_git_force_push(self):
        with patch("demetra.services.rebase.git_force_push", new_callable=AsyncMock) as mock:
            mock.return_value = True
            yield mock

    @pytest.fixture
    def mock_pr_comment(self):
        with patch("demetra.services.rebase.pr_comment", new_callable=AsyncMock) as mock:
            mock.return_value = True
            yield mock

    @pytest.mark.asyncio
    async def test_rebase_success_and_pushed(self, mock_run_command, mock_git_force_push):
        result = await perform_git_rebase(
            worktree_path=WORKTREE_PATH,
            head_branch="feature/branch",
            base_branch="main",
            env=ENV,
        )

        assert result is True
        mock_git_force_push.assert_awaited_once_with(
            target_path=WORKTREE_PATH,
            branch_name="feature/branch",
            env=ENV,
        )

    @pytest.mark.asyncio
    async def test_rebase_success_nothing_to_push_without_pr_info(
        self,
        mock_run_command,
        mock_git_force_push,
        mock_pr_comment,
    ):
        mock_git_force_push.return_value = False

        result = await perform_git_rebase(
            worktree_path=WORKTREE_PATH,
            head_branch="feature/branch",
            base_branch="main",
            env=ENV,
        )

        assert result is True
        mock_pr_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebase_success_nothing_to_push_with_pr_info(
        self,
        mock_run_command,
        mock_git_force_push,
        mock_pr_comment,
    ):
        mock_git_force_push.return_value = False

        result = await perform_git_rebase(
            worktree_path=WORKTREE_PATH,
            head_branch="feature/branch",
            base_branch="main",
            env=ENV,
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        mock_pr_comment.assert_awaited_once_with(
            pr_number=42,
            full_name="owner/repo",
            body="Base branch `main` has no new changes to rebase onto \u2014 already up-to-date.",
            target_path=WORKTREE_PATH,
            env=ENV,
        )

    @pytest.mark.asyncio
    async def test_rebase_success_nothing_to_push_comment_failure(
        self,
        mock_run_command,
        mock_git_force_push,
        mock_pr_comment,
    ):
        mock_git_force_push.return_value = False
        mock_pr_comment.return_value = False

        result = await perform_git_rebase(
            worktree_path=WORKTREE_PATH,
            head_branch="feature/branch",
            base_branch="main",
            env=ENV,
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_rebase_conflict_and_resolved(
        self,
        mock_run_command,
        mock_git_force_push,
    ):
        mock_run_command.side_effect = [
            (1, "", "conflict in file.txt"),  # git rebase fails
            (0, "file.txt\n", ""),  # diff (loop attempt 1) — shows conflicts
            (0, "", ""),  # git rebase --continue succeeds
            (0, "", ""),  # diff (loop attempt 2) — no conflicts → break
            (0, "", ""),  # diff (after loop) — no remaining conflicts
        ]
        with (
            patch("demetra.services.rebase.get_prompt", new_callable=AsyncMock) as mock_get_prompt,
            patch("demetra.services.rebase.opencode_merge_agent", new_callable=AsyncMock) as mock_agent,
            patch("demetra.services.rebase.git_add_all", new_callable=AsyncMock) as mock_add_all,
        ):
            mock_get_prompt.return_value = "resolve this"
            mock_agent.return_value = (0, "", "")
            mock_add_all.return_value = True

            result = await perform_git_rebase(
                worktree_path=WORKTREE_PATH,
                head_branch="feature/branch",
                base_branch="main",
                env=ENV,
            )

            assert result is True
            mock_git_force_push.assert_awaited_once_with(
                target_path=WORKTREE_PATH,
                branch_name="feature/branch",
                env=ENV,
            )

    @pytest.mark.asyncio
    async def test_rebase_conflict_not_resolved(
        self,
        mock_run_command,
        mock_git_force_push,
    ):
        mock_run_command.side_effect = [
            (1, "", "conflict in file.txt"),  # git rebase fails
            (0, "file.txt\n", ""),  # diff (loop attempt 1) — shows conflicts
        ]
        with (
            patch("demetra.services.rebase.get_prompt", new_callable=AsyncMock) as mock_get_prompt,
            patch("demetra.services.rebase.opencode_merge_agent", new_callable=AsyncMock) as mock_agent,
        ):
            mock_get_prompt.return_value = "resolve this"
            mock_agent.return_value = (1, "", "agent failed")

            result = await perform_git_rebase(
                worktree_path=WORKTREE_PATH,
                head_branch="feature/branch",
                base_branch="main",
                env=ENV,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_rebase_continue_fails(
        self,
        mock_run_command,
        mock_git_force_push,
    ):
        mock_run_command.side_effect = [
            (1, "", "conflict in file.txt"),  # git rebase fails
            (0, "file.txt\n", ""),  # diff (loop attempt 1) — shows conflicts
            (1, "", "rebase --continue failed"),  # git rebase --continue fails
        ]
        with (
            patch("demetra.services.rebase.get_prompt", new_callable=AsyncMock) as mock_get_prompt,
            patch("demetra.services.rebase.opencode_merge_agent", new_callable=AsyncMock) as mock_agent,
            patch("demetra.services.rebase.git_add_all", new_callable=AsyncMock) as mock_add_all,
        ):
            mock_get_prompt.return_value = "resolve this"
            mock_agent.return_value = (0, "", "")
            mock_add_all.return_value = True

            result = await perform_git_rebase(
                worktree_path=WORKTREE_PATH,
                head_branch="feature/branch",
                base_branch="main",
                env=ENV,
            )

            assert result is False
