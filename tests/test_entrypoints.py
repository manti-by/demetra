import argparse
import inspect
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.exceptions import AutoCancelledError, PullRequestError
from demetra.library.models import Context, LinearTask, Project, Session
from demetra.settings import DEFAULT_USER_ID, WATCHER_POLL_INTERVAL
from demetra.worker import connection


class TestWatcher:
    def test_poll_interval_value(self):
        assert WATCHER_POLL_INTERVAL == 60


class TestWorker:
    def test_worker_exists(self):
        assert connection is not None


class TestMainEntrypoint:
    def test_main_argparser_accepts_plan_loop(self):
        from main import parser

        assert isinstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--project-name", "demetra", "--plan-loop"])
        assert args.plan_loop is True

    def test_main_argparser_plan_loop_default_false(self):
        from main import parser

        args = parser.parse_args(["--project-name", "demetra"])
        assert args.plan_loop is False

    def test_main_argparser_can_disable_plan_loop(self):
        from main import parser

        args = parser.parse_args(["--project-name", "demetra", "--no-plan-loop"])
        assert args.plan_loop is False

    def test_main_function_accepts_plan_loop_kwarg(self):
        from main import main

        sig = inspect.signature(main)
        assert "plan_loop" in sig.parameters


def _build_context(*, step, build_plan) -> Context:
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
        build_plan=build_plan,
        posted_to_linear=bool(build_plan),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        step=step,
    )
    return Context(
        project=project,
        auto_mode=True,
        linear_task=linear_task,
        branch_name="mnt-128-create-bare-react-application",
        worktree_path=Path("/tmp/worktree/mnt-128-create-bare-react-application"),
        session=session,
    )


class TestMainReplanning:
    """A run that fails before a plan is saved leaves the session step at 'failed' with an
    empty build_plan. main() must re-run the plan step in that case, not only when step is
    'initial' — otherwise the workflow loops forever on 'Empty build plan, exiting.'"""

    @pytest.fixture
    def mock_main_deps(self):
        with (
            patch("main.init_db", new_callable=AsyncMock),
            patch("main.setup_workflow", new_callable=AsyncMock) as mock_setup_workflow,
            patch("main.setup_session_logging", new_callable=AsyncMock),
            patch("main.update_ticket_status", new_callable=AsyncMock) as mock_update_ticket_status,
            patch("demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}),
            patch("main.post_comment", new_callable=AsyncMock) as mock_post_comment,
            patch("main.mark_session_posted", new_callable=AsyncMock),
            patch("main.upsert_pending_session", new_callable=AsyncMock) as mock_upsert_pending_session,
            patch("main.write_session_wiki_page", new_callable=AsyncMock),
            patch("main.run_plan_step", new_callable=AsyncMock) as mock_run_plan_step,
            patch("main.run_build_step", new_callable=AsyncMock) as mock_run_build_step,
            patch("main.commit_and_push", new_callable=AsyncMock) as mock_commit_and_push,
            patch("main.process_pr_failure", new_callable=AsyncMock) as mock_process_pr_failure,
            patch("main.cleanup_workflow", new_callable=AsyncMock) as mock_cleanup_workflow,
        ):
            mock_commit_and_push.return_value = True
            yield {
                "setup_workflow": mock_setup_workflow,
                "update_ticket_status": mock_update_ticket_status,
                "post_comment": mock_post_comment,
                "upsert_pending_session": mock_upsert_pending_session,
                "run_plan_step": mock_run_plan_step,
                "run_build_step": mock_run_build_step,
                "commit_and_push": mock_commit_and_push,
                "process_pr_failure": mock_process_pr_failure,
                "cleanup_workflow": mock_cleanup_workflow,
            }

    @pytest.mark.asyncio
    async def test_main_replans_when_step_failed_but_build_plan_empty(self, mock_main_deps):
        from main import main

        context = _build_context(step="failed", build_plan="")

        async def fake_run_plan_step(context):
            context.session.build_plan = "generated build plan"
            return "generated build plan"

        mock_main_deps["setup_workflow"].return_value = context
        mock_main_deps["run_plan_step"].side_effect = fake_run_plan_step

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["run_plan_step"].assert_awaited_once_with(context=context)
        mock_main_deps["run_build_step"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_skips_replan_when_build_plan_already_present(self, mock_main_deps):
        from main import main

        context = _build_context(step="build", build_plan="existing build plan")
        mock_main_deps["setup_workflow"].return_value = context

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["run_plan_step"].assert_not_awaited()
        mock_main_deps["run_build_step"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_exits_when_replan_produces_no_plan(self, mock_main_deps):
        from main import main

        context = _build_context(step="failed", build_plan="")
        mock_main_deps["setup_workflow"].return_value = context
        mock_main_deps["run_plan_step"].return_value = None

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["run_plan_step"].assert_awaited_once_with(context=context)
        mock_main_deps["run_build_step"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_main_sets_awaiting_input_on_auto_cancelled(self, mock_main_deps):
        from main import main

        context = _build_context(step="initial", build_plan="")
        mock_main_deps["setup_workflow"].return_value = context

        mock_main_deps["run_plan_step"].side_effect = AutoCancelledError

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["cleanup_workflow"].assert_awaited_once_with(
            context=context,
            is_success=False,
            should_update_linear_status=False,
            failure_step="awaiting_input",
        )

    @pytest.mark.asyncio
    async def test_main_delegates_pr_creation_failure_to_failure_step(self, mock_main_deps):
        from main import main

        context = _build_context(step="push", build_plan="existing build plan")
        mock_main_deps["setup_workflow"].return_value = context
        mock_main_deps["commit_and_push"].side_effect = PullRequestError("gh: could not create PR")

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["process_pr_failure"].assert_awaited_once()
        call_kwargs = mock_main_deps["process_pr_failure"].call_args.kwargs
        assert call_kwargs["context"] is context
        assert isinstance(call_kwargs["error"], PullRequestError)
        assert "gh: could not create PR" in str(call_kwargs["error"])
        mock_main_deps["cleanup_workflow"].assert_awaited_once_with(
            context=context,
            is_success=False,
            should_update_linear_status=False,
            failure_step="awaiting_input",
        )

    @pytest.mark.asyncio
    async def test_main_creates_pending_session_when_session_missing(self, mock_main_deps):
        """A console run without a session row must upsert a pending session."""
        from main import main

        context = _build_context(step="initial", build_plan="")
        context.session = None
        mock_main_deps["setup_workflow"].return_value = context
        mock_main_deps["run_plan_step"].return_value = None
        mock_main_deps["upsert_pending_session"].return_value = Session(
            task_id=context.linear_task.id,
            build_plan="",
            posted_to_linear=False,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            step="initial",
        )

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["upsert_pending_session"].assert_awaited_once_with(
            task_id=context.linear_task.id,
            session_id=None,
            project_id=context.project.id,
            user_id=context.linear_task.user_id or DEFAULT_USER_ID,
            name=context.linear_task.full_title,
            linear_link=context.linear_task.url,
        )

    @pytest.mark.asyncio
    async def test_main_skips_pending_session_when_session_exists(self, mock_main_deps):
        """A watcher-created pending session must not be upserted again."""
        from main import main

        context = _build_context(step="initial", build_plan="")
        mock_main_deps["setup_workflow"].return_value = context
        mock_main_deps["run_plan_step"].return_value = None

        await main(project_name="demetra", auto_mode=True)

        mock_main_deps["upsert_pending_session"].assert_not_awaited()
