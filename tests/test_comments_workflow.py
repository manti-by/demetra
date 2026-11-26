from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import AgentFailureError, BuildError, InfiniteLoopError, ReviewError
from demetra.library.models import LinearTask, Session
from demetra.services.comments import resolve_pending_comments
from demetra.workflows.comments import _format_comments_for_summary, run_comments_workflow


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

TASK = LinearTask(
    id="TASK-123",
    kind="linear",
    identifier="TASK-123",
    title="Fix the thing",
    description="Address comments",
)

COMMENTS: list[dict] = [
    {"thread_id": "THREAD_1", "body": "first finding", "path": "a.py", "line": 3, "diff_hunk": "@@ -1 +1 @@"},
    {"thread_id": "THREAD_2", "body": "second finding", "path": "b.py"},
]

PAYLOAD = {
    "batch_id": "batch-1",
    "task_id": "TASK-123",
    "project_id": "proj-1",
    "pr_number": 42,
    "full_name": "owner/repo",
    "comments": COMMENTS,
    "attempt": 0,
}


@pytest.fixture
def base_mocks():
    targets = {
        "get_session": (AsyncMock, None),
        "setup_session_logging": (AsyncMock, None),
        "load_pending_comments": (None, None),
        "get_project_by_id_system": (AsyncMock, None),
        "get_project_environments": (AsyncMock, {}),
        "get_user_environments_decrypted": (AsyncMock, {}),
        "setup_project_venv": (AsyncMock, None),
        "get_pr_info": (AsyncMock, None),
        "git_fetch": (AsyncMock, None),
        "git_worktree_create": (AsyncMock, None),
        "git_worktree_remove": (AsyncMock, None),
        "summarize_findings": (AsyncMock, None),
        "resolve_task_by_id": (AsyncMock, None),
        "run_build_step": (AsyncMock, None),
        "git_add_all": (AsyncMock, None),
        "git_has_unpushed_commits": (AsyncMock, None),
        "git_commit": (AsyncMock, None),
        "git_force_push": (AsyncMock, None),
        "resolve_pending_comments": (AsyncMock, None),
        "pr_comment": (AsyncMock, None),
        "update_session_step": (AsyncMock, None),
        "record_session_step": (AsyncMock, None),
        "clear_pending_comments": (None, None),
        "update_pending_comments": (None, {**PAYLOAD, "attempt": 1}),
        "reset_listener_attempts": (AsyncMock, None),
    }
    with ExitStack() as stack:
        mocks = {}
        for name, (mock_type, return_value) in targets.items():
            target = f"demetra.workflows.comments.{name}"
            if mock_type is None:
                mock = stack.enter_context(patch(target))
            else:
                mock = stack.enter_context(patch(target, new_callable=mock_type))
            if return_value is not None:
                mock.return_value = return_value
            mocks[f"mock_{name}"] = mock

        mocks["mock_get_session"].return_value = SESSION
        mocks["mock_load_pending_comments"].return_value = PAYLOAD
        mocks["mock_get_project_by_id_system"].return_value = PROJECT_DATA
        mocks["mock_get_pr_info"].return_value = ("feature/branch", "master")
        mocks["mock_git_worktree_create"].return_value = Path("/worktree/owner/repo/feature-branch")
        mocks["mock_summarize_findings"].return_value = "1. first finding\n2. second finding"
        mocks["mock_resolve_task_by_id"].return_value = TASK
        mocks["mock_git_add_all"].return_value = True
        mocks["mock_resolve_pending_comments"].return_value = []
        aliases = {
            "mock_load": "mock_load_pending_comments",
            "mock_get_project": "mock_get_project_by_id_system",
            "mock_create": "mock_git_worktree_create",
            "mock_remove": "mock_git_worktree_remove",
            "mock_summarize": "mock_summarize_findings",
            "mock_build": "mock_run_build_step",
            "mock_add": "mock_git_add_all",
            "mock_unpushed": "mock_git_has_unpushed_commits",
            "mock_commit": "mock_git_commit",
            "mock_push": "mock_git_force_push",
            "mock_resolve": "mock_resolve_pending_comments",
            "mock_comment": "mock_pr_comment",
            "mock_step": "mock_update_session_step",
            "mock_record": "mock_record_session_step",
            "mock_clear": "mock_clear_pending_comments",
            "mock_update": "mock_update_pending_comments",
            "mock_reset_attempts": "mock_reset_listener_attempts",
        }
        for alias, original in aliases.items():
            mocks[alias] = mocks[original]
        yield mocks


class TestFormatCommentsForSummary:
    def test_includes_body_path_line_and_diff_hunk(self):
        comments = PAYLOAD["comments"]
        assert isinstance(comments, list)
        result = _format_comments_for_summary(comments)
        assert "Comment 1 — a.py:3" in result
        assert "first finding" in result
        assert "diffHunk: @@ -1 +1 @@" in result
        assert "Comment 2 — b.py" in result

    def test_skips_non_dict_entries(self):
        assert _format_comments_for_summary(["not a comment"]) == ""


class TestResolvePendingComments:
    @pytest.mark.asyncio
    async def test_returns_no_unresolved_threads_without_a_batch(self):
        with (
            patch("demetra.services.comments.resolve_review_threads", new_callable=AsyncMock) as mock_resolve,
            patch("demetra.services.comments.clear_pending_comments") as mock_clear,
        ):
            assert await resolve_pending_comments({"task_id": "TASK-123", "comments": []}, Path("/tmp/repo")) == []
        mock_resolve.assert_not_awaited()
        mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolves_every_thread_and_clears_the_loaded_batch(self):
        with (
            patch(
                "demetra.services.comments.resolve_review_threads", new_callable=AsyncMock, return_value=2
            ) as mock_resolve,
            patch("demetra.services.comments.clear_pending_comments") as mock_clear,
        ):
            assert await resolve_pending_comments(PAYLOAD, Path("/tmp/repo"), project_id="proj-1") == []
            resolve_call = mock_resolve.await_args
            assert resolve_call is not None
            assert resolve_call.kwargs["thread_ids"] == ["THREAD_1", "THREAD_2"]
            mock_clear.assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)

    @pytest.mark.asyncio
    async def test_partial_resolution_keeps_the_batch(self):
        with (
            patch("demetra.services.comments.resolve_review_threads", new_callable=AsyncMock, return_value=1),
            patch("demetra.services.comments.clear_pending_comments") as mock_clear,
        ):
            assert await resolve_pending_comments(PAYLOAD, Path("/tmp/repo")) == ["THREAD_1", "THREAD_2"]
        mock_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_keeps_the_batch(self):
        with (
            patch(
                "demetra.services.comments.resolve_review_threads",
                new_callable=AsyncMock,
                side_effect=RuntimeError("gh failed"),
            ),
            patch("demetra.services.comments.clear_pending_comments") as mock_clear,
        ):
            assert await resolve_pending_comments(PAYLOAD, Path("/tmp/repo")) == ["THREAD_1", "THREAD_2"]
        mock_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_without_thread_ids_is_cleared(self):
        with (
            patch("demetra.services.comments.resolve_review_threads", new_callable=AsyncMock) as mock_resolve,
            patch("demetra.services.comments.clear_pending_comments") as mock_clear,
        ):
            batch = {"task_id": "TASK-123", "comments": [{"body": "note"}]}
            assert await resolve_pending_comments(batch, Path("/tmp/repo")) == []
        mock_resolve.assert_not_awaited()
        mock_clear.assert_called_once_with(task_id="TASK-123", comments=batch)


class TestRunCommentsWorkflow:
    @pytest.mark.asyncio
    async def test_applies_comments_and_resolves_threads(self, base_mocks):
        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is True
        summary = base_mocks["mock_summarize"].await_args.kwargs["review_output"]
        assert "first finding" in summary and "second finding" in summary
        assert base_mocks["mock_build"].await_args.kwargs["build_plan"] == "1. first finding\n2. second finding"
        assert base_mocks["mock_commit"].await_count == 1
        base_mocks["mock_push"].assert_awaited_once()
        base_mocks["mock_resolve"].assert_awaited_once()
        assert [call.kwargs["step"] for call in base_mocks["mock_step"].await_args_list] == [
            "wiki",
            "push",
            "completed",
        ]
        base_mocks["mock_comment"].assert_awaited_once()
        base_mocks["mock_remove"].assert_awaited_once()
        base_mocks["mock_reset_attempts"].assert_awaited_once_with(task_id="TASK-123")

    @pytest.mark.asyncio
    async def test_skips_build_when_summary_is_empty(self, base_mocks):
        base_mocks["mock_summarize"].return_value = None

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is True
        base_mocks["mock_build"].assert_not_awaited()
        base_mocks["mock_push"].assert_not_awaited()
        base_mocks["mock_clear"].assert_called_once()

    @pytest.mark.asyncio
    async def test_no_changes_returns_without_pushing(self, base_mocks):
        base_mocks["mock_add"].return_value = False
        base_mocks["mock_unpushed"].return_value = False

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is True
        base_mocks["mock_push"].assert_not_awaited()
        base_mocks["mock_resolve"].assert_not_awaited()
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)

    @pytest.mark.asyncio
    async def test_records_failure_when_build_raises(self, base_mocks):
        base_mocks["mock_build"].side_effect = RuntimeError("agent failed")

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is False
        base_mocks["mock_push"].assert_not_awaited()
        base_mocks["mock_step"].assert_awaited_with(task_id="TASK-123", step="failed")
        base_mocks["mock_remove"].assert_awaited_once()
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)
        base_mocks["mock_reset_attempts"].assert_awaited_once_with(task_id="TASK-123")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            BuildError("build failed"),
            InfiniteLoopError("loop detected"),
            AgentFailureError(agent="build-agent", stderr="provider failed"),
        ],
    )
    async def test_records_failure_for_demetra_errors(self, base_mocks, error):
        base_mocks["mock_build"].side_effect = error

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is False
        base_mocks["mock_step"].assert_awaited_with(task_id="TASK-123", step="failed")
        base_mocks["mock_record"].assert_awaited_once()
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)
        base_mocks["mock_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_records_failure_when_summarization_fails(self, base_mocks):
        base_mocks["mock_summarize"].side_effect = ReviewError("Failed to summarize the review")

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is False
        base_mocks["mock_build"].assert_not_awaited()
        base_mocks["mock_step"].assert_awaited_with(task_id="TASK-123", step="failed")
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)

    @pytest.mark.asyncio
    async def test_returns_false_when_session_or_batch_is_missing(self, base_mocks):
        base_mocks["mock_get_session"].return_value = None
        assert (
            await run_comments_workflow(task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo")
            is False
        )

        base_mocks["mock_get_session"].return_value = SESSION
        base_mocks["mock_load"].return_value = None
        assert (
            await run_comments_workflow(task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo")
            is False
        )
        assert base_mocks["mock_clear"].call_count == 1

    @pytest.mark.asyncio
    async def test_returns_false_when_project_is_missing(self, base_mocks):
        base_mocks["mock_get_project"].return_value = None
        assert (
            await run_comments_workflow(
                task_id="TASK-123", project_id="proj-missing", pr_number=42, full_name="owner/repo"
            )
            is False
        )
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)

    @pytest.mark.asyncio
    async def test_releases_batch_when_pr_info_or_task_is_missing(self, base_mocks):
        base_mocks["mock_get_pr_info"].return_value = None
        assert (
            await run_comments_workflow(task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo")
            is False
        )
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)

        base_mocks["mock_clear"].reset_mock()
        base_mocks["mock_get_pr_info"].return_value = ("feature/branch", "master")
        base_mocks["mock_resolve_task_by_id"].return_value = None
        assert (
            await run_comments_workflow(task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo")
            is False
        )
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)

    @pytest.mark.asyncio
    async def test_retains_batch_for_retry_when_resolution_fails(self, base_mocks):
        base_mocks["mock_resolve"].return_value = ["THREAD_1", "THREAD_2"]

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is False
        base_mocks["mock_push"].assert_awaited_once()
        base_mocks["mock_step"].assert_awaited_with(task_id="TASK-123", step="failed")
        assert any(
            "Unresolved CodeRabbit threads" in call.kwargs.get("message", "")
            for call in base_mocks["mock_record"].await_args_list
        )
        base_mocks["mock_update"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD, updates={"attempt": 1})
        base_mocks["mock_clear"].assert_not_called()
        base_mocks["mock_comment"].assert_not_awaited()
        base_mocks["mock_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_releases_batch_when_initialization_fails(self, base_mocks):
        base_mocks["mock_setup_session_logging"].side_effect = RuntimeError("logging failed")

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is False
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)
        base_mocks["mock_reset_attempts"].assert_awaited_once_with(task_id="TASK-123")

    @pytest.mark.asyncio
    async def test_removes_worktree_when_attempt_reset_fails(self, base_mocks):
        base_mocks["mock_reset_attempts"].side_effect = RuntimeError("database failed")

        result = await run_comments_workflow(
            task_id="TASK-123", project_id="proj-1", pr_number=42, full_name="owner/repo"
        )

        assert result is True
        base_mocks["mock_clear"].assert_called_once_with(task_id="TASK-123", comments=PAYLOAD)
        base_mocks["mock_remove"].assert_awaited_once()
