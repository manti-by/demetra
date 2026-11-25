from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import (
    AgentBudgetRetryError,
    AgentCompactionError,
    AgentContextOverflowError,
    AgentNetworkError,
    AgentPermissionError,
    AgentProviderError,
    AgentQuotaError,
    AgentRateLimitError,
    BuildError,
    LinearError,
    PullRequestError,
    ReviewError,
    WikiError,
)
from demetra.library.models import Chat, Context, LinearTask, Project, Session, SessionEnvironment
from demetra.services.linear.states import LinearState
from demetra.settings import LINEAR
from demetra.workflows.failure import (
    process_agent_failure,
    process_agent_network_failure,
    process_build_failure,
    process_pr_failure,
    process_wiki_failure,
)


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
        task=linear_task,
        branch_name="mnt-128-create-bare-react-application",
        worktree_path=Path("/tmp/worktree/mnt-128-create-bare-react-application"),
        session=session,
    )


def build_chat_context() -> Context:
    context = build_context()
    context.task = Chat(
        id="CH-1",
        identifier="CH-1",
        title="Chat task",
        description="desc",
        created_at=datetime.now().isoformat(),
    )
    return context


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
            mock_post_comment.return_value = f"comment-{uuid4().hex[:8]}"
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
            task_id=context.task.id,
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
            task_id=context.task.id,
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
            task_id=context.task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_posts_agent_network_failure_comment(self, mock_linear_deps):
        context = build_context()
        error = AgentNetworkError(agent="build-agent", stderr="read ECONNRESET")

        await process_agent_network_failure(context=context, error=error)

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "Agent network failure" in body
        assert "build-agent" in body
        assert "read ECONNRESET" in body

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.task.id,
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
            task_id=context.task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_moves_to_the_named_awaiting_input_column(self, mock_linear_deps):
        """A configured id pointing at another column must not win: the ticket
        has to land in the column named Awaiting Input."""
        context = build_context()

        with (
            patch.object(SessionEnvironment, "linear_state", return_value="state-failed"),
            patch.object(SessionEnvironment, "linear_value", return_value="team-123"),
            patch(
                "demetra.services.linear.states.fetch_team_states",
                new_callable=AsyncMock,
                return_value=[
                    LinearState(id="state-failed", name="Failed", type="started"),
                    LinearState(id="state-awaiting", name="Awaiting Input", type="started"),
                ],
            ),
        ):
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.task.id,
            state_id="state-awaiting",
        )

    @pytest.mark.asyncio
    async def test_refuses_a_mis_pointed_id_when_the_column_is_missing(self, mock_linear_deps):
        """A team without an Awaiting Input column must not leave the ticket in
        the column the configured id points at."""
        context = build_context()

        with (
            patch.object(SessionEnvironment, "linear_state", return_value="state-failed"),
            patch.object(SessionEnvironment, "linear_value", return_value="team-123"),
            patch(
                "demetra.services.linear.states.fetch_team_states",
                new_callable=AsyncMock,
                return_value=[LinearState(id="state-failed", name="Failed", type="started")],
            ),
            patch("demetra.workflows.failure.print_message") as mock_print_message,
        ):
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        mock_linear_deps["update_ticket_status"].assert_not_awaited()
        messages = [call.args[0] for call in mock_print_message.call_args_list]
        assert any("move it manually" in message for message in messages)

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
    async def test_moves_to_awaiting_input_when_the_local_copy_fails(self, mock_linear_deps):
        """A failed local copy must not stop the ticket from moving to Awaiting Input."""
        context = build_context()

        with patch(
            "demetra.services.linear.mirror.upsert_message",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("database is down"),
        ):
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_reports_failed_comment(self, mock_linear_deps):
        context = build_context()
        mock_linear_deps["post_comment"].return_value = False

        with patch("demetra.workflows.failure.print_message") as mock_print_message:
            await process_pr_failure(context=context, error=PullRequestError("gh: could not create PR"))

        messages = [call.args[0] for call in mock_print_message.call_args_list]
        assert any("Failed to post PR-creation-failure comment" in message for message in messages)

    @pytest.mark.parametrize(
        "error, heading",
        [
            (AgentQuotaError(agent="plan-agent", stderr="credits exhausted"), "Agent credits exhausted"),
            (AgentBudgetRetryError(agent="plan-agent", stderr="budget rejected"), "Agent budget rejection"),
            (AgentRateLimitError(agent="build-agent", stderr="rate limit"), "Agent rate limited"),
            (AgentPermissionError(agent="build-agent", stderr="permission denied"), "Agent permission denied"),
            (AgentContextOverflowError(agent="validate-agent", stderr="context overflow"), "Agent context overflow"),
            (AgentProviderError(agent="research-agent", stderr="server error"), "Agent provider error"),
            (
                AgentCompactionError(agent="build-agent", stderr="compaction unavailable"),
                "Agent compaction unavailable",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_posts_classified_agent_failure_comment(self, mock_linear_deps, error, heading):
        context = build_context()

        await process_agent_failure(context=context, error=error)

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert heading in body
        assert error.agent in body
        assert error.code in body
        assert error.stderr in body
        assert "{retry_hint}" not in body
        mock_linear_deps["update_ticket_status"].assert_awaited_once_with(
            task_id=context.task.id,
            state_id=LINEAR["states"]["awaiting_input"],
        )

    @pytest.mark.asyncio
    async def test_classified_error_comment_keeps_redacted_text(self, mock_linear_deps):
        error = AgentQuotaError(agent="plan-agent", stderr="credits exhausted for [redacted-key]")

        await process_agent_failure(context=build_context(), error=error)

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "[redacted-key]" in body

    @pytest.mark.asyncio
    async def test_retryable_and_non_retryable_hints(self, mock_linear_deps):
        retryable = AgentRateLimitError(agent="plan-agent", stderr="rate limit", retry_after_ms=500)
        terminal = AgentQuotaError(agent="plan-agent", stderr="credits exhausted")

        await process_agent_failure(context=build_context(), error=retryable)
        retryable_body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        await process_agent_failure(context=build_context(), error=terminal)
        terminal_body = mock_linear_deps["post_comment"].await_args.kwargs["body"]

        assert "Wait at least 500 ms before retrying" in retryable_body
        assert "Retrying will not help" in terminal_body

    @pytest.mark.parametrize(
        "error",
        [
            AgentBudgetRetryError(agent="plan-agent", stderr="budget rejected"),
            AgentCompactionError(agent="build-agent", stderr="compaction unavailable"),
            AgentContextOverflowError(agent="validate-agent", stderr="context overflow"),
            AgentPermissionError(agent="build-agent", stderr="permission denied"),
        ],
    )
    @pytest.mark.asyncio
    async def test_chat_failure_recovery_does_not_mention_a_linear_ticket(self, error):
        with patch("demetra.workflows.failure.notify_message", new_callable=AsyncMock, return_value=True) as notify:
            await process_agent_failure(context=build_chat_context(), error=error)

        assert notify.await_args is not None
        body = notify.await_args.kwargs["body"]
        assert "In Progress" not in body
        assert "Send another message in this chat to re-run." in body

    @pytest.mark.asyncio
    async def test_linear_failure_recovery_keeps_the_ticket_instructions(self, mock_linear_deps):
        error = AgentContextOverflowError(agent="validate-agent", stderr="context overflow")

        await process_agent_failure(context=build_context(), error=error)

        body = mock_linear_deps["post_comment"].await_args.kwargs["body"]
        assert "Move the ticket back to `In Progress` to re-run." in body
