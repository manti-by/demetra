from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.exceptions import BuildError, LinearError, PullRequestError, ReviewError, WikiError
from demetra.library.models import Context, LinearTask, Project, Session
from demetra.settings import LINEAR
from demetra.workflows.failure import process_build_failure, process_pr_failure, process_wiki_failure


def build_context() -> Context:
    linear_task = LinearTask(
        id=str(uuid4()),
        identifier="MNT-128",
        title="Create Bare React Application",
        description="desc",
        priority=1,
        created_at=datetime.now().isoformat(),
    )
    project = Project(
        id=str(uuid4()),
        user_id=str(uuid4()),
        linear_project_id=None,
        name="demetra",
        state="active",
        repository_url="https://github.com/test/demetra",
        repository_name="demetra",
        repository_owner="test",
        local_path=Path("/tmp/demetra"),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    session = Session(
        task_id=linear_task.id,
        build_plan="existing build plan",
        posted_to_linear=True,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        step="push",
    )
    return Context(
        project=project,
        auto_mode=True,
        linear_task=linear_task,
        branch_name="mnt-128-create-bare-react-application",
        worktree_path=Path("/tmp/worktree/mnt-128-create-bare-react-application"),
        session=session,
    )


class TestRunFailureStep:
    @pytest.fixture
    def mock_linear_deps(self):
        with (
            patch("demetra.workflows.failure.post_comment", new_callable=AsyncMock) as mock_post_comment,
            patch(
                "demetra.workflows.failure.update_ticket_status", new_callable=AsyncMock
            ) as mock_update_ticket_status,
            patch("demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}),
        ):
            mock_post_comment.return_value = True
            mock_update_ticket_status.return_value = True
            yield {"post_comment": mock_post_comment, "update_ticket_status": mock_update_ticket_status}

    @pytest.mark.asyncio
    async def test_posts_comment_with_recovery_details(self, mock_linear_deps):
        context = build_context()

        await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "PR creation failed" in body
        assert "mnt-128-create-bare-react-application" in body
        assert "https://github.com/test/demetra/compare/mnt-128-create-bare-react-application" in body
        assert "gh: could not create PR" in body

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.linear_task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_posts_review_failure_comment(self, mock_linear_deps):
        context = build_context()

        await process_pr_failure(context=context, error=ReviewError("Failed to summarize the review"))

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "Review summarization failed" in body
        assert "Failed to summarize the review" in body

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.linear_task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_posts_build_failure_comment(self, mock_linear_deps):
        context = build_context()
        error = BuildError("Build agent failed (exit 1): Unexpected server error")

        await process_build_failure(context=context, error=error)

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "Build agent failed" in body
        assert "Unexpected server error" in body

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.linear_task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_posts_wiki_failure_comment(self, mock_linear_deps):
        context = build_context()
        error = WikiError("Failed to write wiki page for MNT-128: disk full")

        await process_wiki_failure(context=context, error=error)

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "Wiki page generation failed" in body
        assert "Failed to write wiki page for MNT-128: disk full" in body

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.linear_task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_reports_failed_status_update(self, mock_linear_deps):
        """A failed Awaiting Input update must surface a manual-recovery message instead of
        silently recording awaiting_input while Linear stays in another state."""
        context = build_context()
        mock_linear_deps["update_ticket_status"].return_value = False

        with patch("demetra.workflows.failure.print_message") as mock_print_message:
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        messages = [call.args[0] for call in mock_print_message.call_args_list]
        assert any("move it manually" in message for message in messages)

    @pytest.mark.asyncio
    async def test_handles_linear_error(self, mock_linear_deps):
        """LinearError raised by post_comment/update_ticket_status must not escape the failure step."""
        context = build_context()
        mock_linear_deps["post_comment"].side_effect = LinearError("Linear API error")

        with patch("demetra.workflows.failure.print_message") as mock_print_message:
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        messages = [call.args[0] for call in mock_print_message.call_args_list]
        assert any("Failed to update Linear" in message for message in messages)

    @pytest.mark.asyncio
    async def test_reports_failed_comment(self, mock_linear_deps):
        context = build_context()
        mock_linear_deps["post_comment"].return_value = False

        with patch("demetra.workflows.failure.print_message") as mock_print_message:
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        messages = [call.args[0] for call in mock_print_message.call_args_list]
        assert any("Failed to post PR-creation-failure comment" in message for message in messages)
