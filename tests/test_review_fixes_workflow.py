from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import WikiError
from demetra.library.models import LinearTask, Session
from demetra.services import wiki as wiki_service
from demetra.workflows.review_fixes import run_review_fixes_workflow


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
    identifier="MNT-123",
    title="Address review threads",
    description="Fix findings",
)

THREADS: list[dict] = [
    {
        "path": "demetra/app.py",
        "line": 12,
        "isOutdated": False,
        "comments": {"nodes": [{"body": "Handle missing header", "author": {"login": "reviewer"}}]},
    }
]


@pytest.fixture
def base_mocks(tmp_path: Path):
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    with (
        patch("demetra.workflows.review_fixes.get_session", new_callable=AsyncMock) as mock_get_session,
        patch("demetra.workflows.review_fixes.setup_session_logging", new_callable=AsyncMock),
        patch("demetra.workflows.review_fixes.get_project_by_id_system", new_callable=AsyncMock) as mock_get_project,
        patch("demetra.workflows.review_fixes.get_project_environments", new_callable=AsyncMock) as mock_get_env,
        patch(
            "demetra.workflows.review_fixes.get_user_environments_decrypted", new_callable=AsyncMock
        ) as mock_get_user_env,
        patch("demetra.workflows.review_fixes.setup_project_venv", new_callable=AsyncMock),
        patch("demetra.workflows.review_fixes.get_pr_info", new_callable=AsyncMock) as mock_pr_info,
        patch("demetra.workflows.review_fixes.git_fetch", new_callable=AsyncMock),
        patch("demetra.workflows.review_fixes.git_worktree_create", new_callable=AsyncMock) as mock_wt_create,
        patch("demetra.workflows.review_fixes.git_worktree_remove", new_callable=AsyncMock) as mock_wt_remove,
        patch("demetra.workflows.review_fixes.get_unresolved_review_threads", new_callable=AsyncMock) as mock_threads,
        patch("demetra.workflows.review_fixes.opencode_review_fixes_agent", new_callable=AsyncMock) as mock_agent,
        patch("demetra.workflows.review_fixes.git_add_all", new_callable=AsyncMock) as mock_add_all,
        patch("demetra.workflows.review_fixes.git_has_unpushed_commits", new_callable=AsyncMock) as mock_has_unpushed,
        patch("demetra.workflows.review_fixes.git_commit", new_callable=AsyncMock) as mock_commit,
        patch("demetra.workflows.review_fixes.git_force_push", new_callable=AsyncMock) as mock_push,
        patch("demetra.workflows.review_fixes.pr_comment", new_callable=AsyncMock) as mock_pr_comment,
        patch("demetra.workflows.review_fixes.resolve_task_by_id", new_callable=AsyncMock) as mock_resolve_task,
        patch("demetra.workflows.review_fixes.write_session_wiki_page", new_callable=AsyncMock) as mock_write_wiki,
        patch("demetra.workflows.review_fixes.print_message"),
    ):
        mock_get_session.return_value = SESSION
        mock_get_project.return_value = PROJECT_DATA
        mock_get_env.return_value = {}
        mock_get_user_env.return_value = {}
        mock_pr_info.return_value = ("feature/branch", "master")
        mock_wt_create.return_value = worktree_path
        mock_threads.return_value = THREADS
        mock_agent.return_value = (0, "ok", "")
        mock_add_all.return_value = True
        mock_has_unpushed.return_value = False
        mock_pr_comment.return_value = True
        mock_resolve_task.return_value = TASK
        yield {
            "worktree_path": worktree_path,
            "mock_wt_remove": mock_wt_remove,
            "mock_add_all": mock_add_all,
            "mock_has_unpushed": mock_has_unpushed,
            "mock_commit": mock_commit,
            "mock_push": mock_push,
            "mock_pr_comment": mock_pr_comment,
            "mock_resolve_task": mock_resolve_task,
            "mock_write_wiki": mock_write_wiki,
        }


class TestRunReviewFixesWorkflow:
    @pytest.mark.asyncio
    async def test_writes_wiki_to_worktree_stages_and_commits_before_push(self, base_mocks):
        events: list[str] = []
        worktree_path = base_mocks["worktree_path"]

        async def record_add(**kwargs):
            events.append("add")
            return True

        async def record_wiki(*, context, wiki_root):
            events.append("wiki")
            assert wiki_root == worktree_path / "wiki"
            assert context.worktree_path == worktree_path

        async def record_commit(**kwargs):
            events.append("commit")

        async def record_push(**kwargs):
            events.append("push")

        async def record_remove(**kwargs):
            events.append("remove")

        base_mocks["mock_add_all"].side_effect = record_add
        base_mocks["mock_write_wiki"].side_effect = record_wiki
        base_mocks["mock_commit"].side_effect = record_commit
        base_mocks["mock_push"].side_effect = record_push
        base_mocks["mock_wt_remove"].side_effect = record_remove

        result = await run_review_fixes_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        assert events == ["add", "wiki", "add", "commit", "push", "remove"]
        assert list(wiki_service.PAGES_ROOT.glob("*.md")) == []
        assert not wiki_service.INDEX_PATH.exists()

    @pytest.mark.asyncio
    async def test_commits_wiki_when_agent_already_committed_changes(self, base_mocks):
        base_mocks["mock_add_all"].side_effect = [False, True]
        base_mocks["mock_has_unpushed"].return_value = True

        result = await run_review_fixes_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        base_mocks["mock_write_wiki"].assert_awaited_once()
        assert base_mocks["mock_write_wiki"].await_args.kwargs["wiki_root"] == base_mocks["worktree_path"] / "wiki"
        assert base_mocks["mock_add_all"].await_count == 2
        base_mocks["mock_commit"].assert_awaited_once()
        base_mocks["mock_push"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wiki_failure_is_best_effort_and_still_commits_staged_fixes(self, base_mocks):
        base_mocks["mock_write_wiki"].side_effect = WikiError("LLM unavailable")

        result = await run_review_fixes_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        base_mocks["mock_add_all"].assert_awaited_once()
        base_mocks["mock_commit"].assert_awaited_once()
        base_mocks["mock_push"].assert_awaited_once()
        base_mocks["mock_wt_remove"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_changes_skips_wiki_write_and_commit(self, base_mocks):
        base_mocks["mock_add_all"].return_value = False
        base_mocks["mock_has_unpushed"].return_value = False

        result = await run_review_fixes_workflow(
            task_id="TASK-123",
            project_id="proj-1",
            pr_number=42,
            full_name="owner/repo",
        )

        assert result is True
        base_mocks["mock_write_wiki"].assert_not_awaited()
        base_mocks["mock_commit"].assert_not_awaited()
        base_mocks["mock_push"].assert_not_awaited()
