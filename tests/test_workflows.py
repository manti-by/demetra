from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.exceptions import AutoCancelledError, InfiniteLoopError, LinearError, PlanError
from demetra.library.models import Context, LinearTask, Project, Session, SessionHistory, TokenUsage
from demetra.services.agents.opencode import RESEARCH_HEADER_STRING
from demetra.workflows.build import check_and_compact_context, run_build_step
from demetra.workflows.cleanup import PullRequestError, cleanup_workflow, commit_and_push
from demetra.workflows.lint import run_lint_and_test
from demetra.workflows.plan import run_plan_step
from demetra.workflows.research import is_research_ticket, run_research_step
from demetra.workflows.resolve import run_resolve_step
from demetra.workflows.review import run_review_agents
from demetra.workflows.setup import setup_workflow


class TestWorkflowSetup:
    @pytest.fixture
    def mock_search_projects(self):
        with patch("demetra.workflows.setup.search_projects_by_name", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_environments(self):
        with patch("demetra.workflows.setup.get_project_environments", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_user_environments(self):
        with patch("demetra.workflows.setup.get_user_environments_decrypted", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_setup_project_venv(self):
        with patch("demetra.workflows.setup.setup_project_venv", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_linear_task(self):
        with patch("demetra.workflows.setup.get_linear_task", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_session(self):
        with patch("demetra.workflows.setup.get_session", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_git_pull(self):
        with patch("demetra.workflows.setup.git_pull", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_git_worktree_create(self):
        with patch("demetra.workflows.setup.git_worktree_create", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_setup_deps(
        self,
        mock_search_projects,
        mock_get_environments,
        mock_get_user_environments,
        mock_setup_project_venv,
        mock_get_linear_task,
        mock_get_session,
        mock_git_pull,
        mock_git_worktree_create,
    ):
        return (
            mock_search_projects,
            mock_get_environments,
            mock_get_user_environments,
            mock_setup_project_venv,
            mock_get_linear_task,
            mock_get_session,
            mock_git_pull,
            mock_git_worktree_create,
        )

    @pytest.mark.asyncio
    async def test_setup_workflow_returns_context(self, faker, mock_setup_deps):
        (
            mock_search,
            mock_env,
            mock_user_env,
            _mock_venv,
            mock_task,
            mock_sess,
            _mock_pull,
            mock_wt,
        ) = mock_setup_deps
        project_data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "linear_project_id": str(uuid4()),
            "name": "demetra",
            "state": "active",
            "repository_url": "https://github.com/test/demetra",
            "repository_name": "demetra",
            "repository_owner": "test",
            "local_path": f"/tmp/{faker.slug()}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        linear_task_data = {
            "id": str(uuid4()),
            "identifier": "MNT-123",
            "title": faker.sentence(),
            "description": faker.text(),
            "priority": "1",
            "created_at": datetime.now().isoformat(),
            "comments": [],
        }

        mock_search.return_value = [project_data]
        mock_env.return_value = {}
        mock_user_env.return_value = {}
        mock_task.return_value = LinearTask(**linear_task_data)  # ty: ignore
        mock_sess.return_value = None
        mock_wt.return_value = f"/tmp/worktree/{faker.slug()}"

        result = await setup_workflow("demetra", auto_mode=False)

        assert result is not None
        assert result.project.name == "demetra"

    @pytest.mark.asyncio
    async def test_setup_workflow_project_not_found(self, mock_search_projects):
        mock_search_projects.return_value = []
        result = await setup_workflow("nonexistent", auto_mode=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_setup_workflow_multiple_projects_found(self, faker, mock_search_projects):
        project_data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "linear_project_id": str(uuid4()),
            "name": "demetra",
            "state": "active",
            "repository_url": "https://github.com/test/demetra",
            "repository_name": "demetra",
            "repository_owner": "test",
            "local_path": f"/tmp/{faker.slug()}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        mock_search_projects.return_value = [project_data, project_data]
        result = await setup_workflow("demetra", auto_mode=False)
        assert result is None


class TestWorkflowPlan:
    @pytest.fixture
    def mock_plan_agent(self):
        with patch("demetra.workflows.plan.opencode_plan_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_extract_plan(self):
        with patch("demetra.workflows.plan.extract_plan", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_extract_questions(self):
        with patch("demetra.workflows.plan.extract_questions", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_save_session(self):
        with patch("demetra.workflows.plan.save_session", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_opencode_session_id(self):
        with patch("demetra.workflows.plan.get_opencode_session_id", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture(autouse=True)
    def _mock_record_session_step_history(self):
        with patch("demetra.workflows.plan.record_session_step_history", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_run_plan_step_returns_build_plan(
        self,
        faker,
        mock_plan_agent,
        mock_extract_plan,
        mock_extract_questions,
        mock_save_session,
        mock_get_opencode_session_id,
    ):
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_plan_agent.return_value = (0, f"## Implementation Plan\n{faker.text()}", "")
        mock_extract_plan.return_value = "build plan content"
        mock_extract_questions.return_value = []
        mock_get_opencode_session_id.return_value = None

        result = await run_plan_step(context)

        assert result == "build plan content"

    @pytest.mark.asyncio
    async def test_run_plan_step_empty_plan_returns_none(
        self,
        faker,
        mock_plan_agent,
        mock_extract_plan,
    ):
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_plan_agent.return_value = (0, f"## Implementation Plan\n{faker.text()}", "")
        mock_extract_plan.return_value = None

        result = await run_plan_step(context)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_plan_step_moves_to_awaiting_input_on_summarization_failure(
        self,
        faker,
        mock_plan_agent,
        mock_extract_plan,
    ):
        with (
            patch("demetra.workflows.plan.post_comment", new_callable=AsyncMock) as mock_post_comment,
            patch("demetra.workflows.plan.update_ticket_status", new_callable=AsyncMock) as mock_update_ticket_status,
            patch("demetra.workflows.plan.update_session_step", new_callable=AsyncMock) as mock_update_session_step,
            patch(
                "demetra.workflows.plan.get_linear_config_value",
                new_callable=AsyncMock,
                return_value="awaiting-input-state-id",
            ),
        ):
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
                    priority=1,
                    created_at=datetime.now().isoformat(),
                ),
                branch_name="feature/test",
                worktree_path=Path(f"/tmp/{faker.slug()}"),
                session=None,
            )

            mock_plan_agent.return_value = (0, faker.text(), "")
            mock_extract_plan.side_effect = PlanError("Failed to summarize the build plan")

            with pytest.raises(AutoCancelledError):
                await run_plan_step(context)

            mock_post_comment.assert_awaited_once()
            mock_update_ticket_status.assert_awaited_once_with(
                task_id=context.linear_task.id, state_id="awaiting-input-state-id"
            )
            mock_update_session_step.assert_any_await(task_id=context.linear_task.id, step="awaiting_input")

    @pytest.mark.asyncio
    async def test_run_plan_step_empty_agent_output_moves_to_awaiting_input(
        self,
        faker,
        mock_plan_agent,
        mock_extract_plan,
    ):
        with (
            patch("demetra.workflows.plan.post_comment", new_callable=AsyncMock) as mock_post_comment,
            patch("demetra.workflows.plan.update_ticket_status", new_callable=AsyncMock) as mock_update_ticket_status,
            patch("demetra.workflows.plan.update_session_step", new_callable=AsyncMock) as mock_update_session_step,
            patch(
                "demetra.workflows.plan.get_linear_config_value",
                new_callable=AsyncMock,
                return_value="awaiting-input-state-id",
            ),
        ):
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
                    priority=1,
                    created_at=datetime.now().isoformat(),
                ),
                branch_name="feature/test",
                worktree_path=Path(f"/tmp/{faker.slug()}"),
                session=None,
            )

            mock_plan_agent.return_value = (0, "  \n\t\n  ", "")

            with pytest.raises(AutoCancelledError):
                await run_plan_step(context)

            mock_extract_plan.assert_not_called()
            mock_post_comment.assert_awaited_once()
            mock_update_ticket_status.assert_awaited_once_with(
                task_id=context.linear_task.id, state_id="awaiting-input-state-id"
            )
            mock_update_session_step.assert_any_await(task_id=context.linear_task.id, step="awaiting_input")

    @pytest.mark.asyncio
    async def test_run_plan_step_output_missing_plan_header_moves_to_awaiting_input(
        self,
        faker,
        mock_plan_agent,
        mock_extract_plan,
    ):
        with (
            patch("demetra.workflows.plan.post_comment", new_callable=AsyncMock) as mock_post_comment,
            patch("demetra.workflows.plan.update_ticket_status", new_callable=AsyncMock) as mock_update_ticket_status,
            patch("demetra.workflows.plan.update_session_step", new_callable=AsyncMock) as mock_update_session_step,
            patch(
                "demetra.workflows.plan.get_linear_config_value",
                new_callable=AsyncMock,
                return_value="awaiting-input-state-id",
            ),
        ):
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
                    priority=1,
                    created_at=datetime.now().isoformat(),
                ),
                branch_name="feature/test",
                worktree_path=Path(f"/tmp/{faker.slug()}"),
                session=None,
            )

            mock_plan_agent.return_value = (0, faker.text(), "")

            with pytest.raises(AutoCancelledError):
                await run_plan_step(context)

            mock_extract_plan.assert_not_called()
            mock_post_comment.assert_awaited_once()
            mock_update_ticket_status.assert_awaited_once_with(
                task_id=context.linear_task.id, state_id="awaiting-input-state-id"
            )
            mock_update_session_step.assert_any_await(task_id=context.linear_task.id, step="awaiting_input")


class TestWorkflowResolve:
    @pytest.fixture
    def mock_resolve_agent(self):
        with patch("demetra.workflows.resolve.opencode_resolve_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_prompt(self):
        with patch("demetra.workflows.resolve.get_prompt", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_resolve_deps(self, mock_resolve_agent, mock_get_prompt):
        return mock_resolve_agent, mock_get_prompt

    @pytest.mark.asyncio
    async def test_run_resolve_step_passes_task_and_questions(self, faker, mock_resolve_deps):

        mock_agent, mock_prompt = mock_resolve_deps
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
            auto_mode=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        original_task = "build something"
        questions = ["What is X?", "What is Y?"]
        resolved_prompt = (
            "Original Task:\nbuild something\n\n"
            "Open Questions to Resolve:\n1. What is X?\n2. What is Y?\n\n"
            "Answer each question by inspecting the codebase."
        )

        mock_agent.return_value = (0, "answer text", None)
        mock_prompt.return_value = resolved_prompt

        result = await run_resolve_step(context=context, original_task=original_task, questions=questions)

        assert result == "answer text"
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args.kwargs
        task_passed = call_kwargs.get("task", "")
        assert task_passed == resolved_prompt
        assert "build something" in task_passed
        assert "What is X?" in task_passed
        assert "What is Y?" in task_passed
        assert call_kwargs.get("task_title") is not None
        mock_prompt.assert_awaited_once_with(
            "resolve_questions",
            original_task=original_task,
            numbered_questions="1. What is X?\n2. What is Y?",
        )

    @pytest.mark.asyncio
    async def test_run_resolve_step_uses_new_session(self, faker, mock_resolve_deps):

        mock_agent, mock_prompt = mock_resolve_deps
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
            auto_mode=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_agent.return_value = (0, "answers", None)
        mock_prompt.return_value = "prompt text"

        await run_resolve_step(context=context, original_task="task", questions=["q?"])

        call_kwargs = mock_agent.call_args.kwargs
        assert "session_id" not in call_kwargs or call_kwargs.get("session_id") is None


class TestWorkflowPlanLoop:
    @pytest.fixture
    def mock_plan_agent(self):
        with patch("demetra.workflows.plan.opencode_plan_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_extract_plan(self):
        with patch("demetra.workflows.plan.extract_plan", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_extract_questions(self):
        with patch("demetra.workflows.plan.extract_questions", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_resolve_step(self):
        with patch("demetra.workflows.plan.run_resolve_step", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_save_session(self):
        with patch("demetra.workflows.plan.save_session", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_opencode_session_id(self):
        with patch("demetra.workflows.plan.get_opencode_session_id", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_post_comment(self):
        with patch("demetra.workflows.plan.post_comment", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_update_ticket_status(self):
        with patch("demetra.workflows.plan.update_ticket_status", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_record_session_step_history(self):
        with patch("demetra.workflows.plan.record_session_step_history", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_update_session_step(self):
        with patch("demetra.workflows.plan.update_session_step", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_max_plan_attempts_3(self):
        with patch("demetra.workflows.plan.MAX_PLAN_ATTEMPTS", 3):
            yield

    @pytest.fixture
    def mock_max_plan_attempts_2(self):
        with patch("demetra.workflows.plan.MAX_PLAN_ATTEMPTS", 2):
            yield

    @pytest.fixture(autouse=True)
    def _auto_mock_record_session_step_history(self, mock_record_session_step_history):
        pass

    @pytest.fixture(autouse=True)
    def _auto_mock_update_session_step(self, mock_update_session_step):
        pass

    @pytest.fixture(autouse=True)
    def _mock_empty_user_environment(self):
        with patch("demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}):
            yield

    @pytest.fixture
    def mock_plan_loop_base(
        self,
        mock_plan_agent,
        mock_extract_plan,
        mock_extract_questions,
        mock_save_session,
        mock_get_opencode_session_id,
    ):
        return (
            mock_plan_agent,
            mock_extract_plan,
            mock_extract_questions,
            mock_save_session,
            mock_get_opencode_session_id,
        )

    @pytest.mark.asyncio
    async def test_plan_loop_calls_resolve_and_revalidates(
        self,
        faker,
        mock_plan_loop_base,
        mock_run_resolve_step,
        mock_max_plan_attempts_3,
    ):
        mock_plan_agent, mock_extract_plan, mock_extract_questions, _mock_save_session, mock_get_opencode_session_id = (
            mock_plan_loop_base
        )
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
            auto_mode=True,
            plan_loop=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        plan_outputs = [
            (0, "Plan v1\n## Implementation Plan\ncontent\nPlease check my questions above.", None),
            (0, "Plan v2\n## Implementation Plan\nReady to proceed to build.", None),
        ]
        plan_calls = []

        async def mock_plan_side_effect(*args, **kwargs):
            plan_calls.append(kwargs.get("task", ""))
            if plan_calls and "Resolved Answers" in plan_calls[-1]:
                return plan_outputs[1]
            return plan_outputs[0]

        extract_plan_results = ["build plan v1", "build plan v2"]
        extract_question_results = [["How does X work?"], []]

        mock_plan_agent.side_effect = mock_plan_side_effect
        mock_extract_plan.side_effect = extract_plan_results
        mock_extract_questions.side_effect = extract_question_results
        mock_run_resolve_step.return_value = "resolved answers"
        mock_get_opencode_session_id.return_value = None

        result = await run_plan_step(context)

        assert result == "build plan v2"
        assert mock_run_resolve_step.call_count == 1
        assert len(plan_calls) == 2
        assert "Resolved Answers" in plan_calls[1]

    @pytest.mark.asyncio
    async def test_plan_loop_max_attempts_raises(
        self,
        faker,
        mock_plan_loop_base,
        mock_run_resolve_step,
        mock_max_plan_attempts_2,
    ):

        mock_plan_agent, mock_extract_plan, mock_extract_questions, _mock_save_session, mock_get_opencode_session_id = (
            mock_plan_loop_base
        )
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
            auto_mode=True,
            plan_loop=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_plan_agent.return_value = (
            0,
            "Plan\n## Implementation Plan\ncontent\nPlease check my questions above.",
            None,
        )
        mock_extract_plan.return_value = "build plan"
        mock_extract_questions.return_value = ["What is X?"]
        mock_run_resolve_step.return_value = "answers"
        mock_get_opencode_session_id.return_value = None

        with pytest.raises(InfiniteLoopError):
            await run_plan_step(context)

        assert mock_run_resolve_step.call_count == 1

    @pytest.mark.asyncio
    async def test_plan_loop_disabled_uses_linear_auto_mode(
        self,
        faker,
        mock_plan_loop_base,
        mock_run_resolve_step,
        mock_post_comment,
        mock_update_ticket_status,
    ):

        mock_plan_agent, mock_extract_plan, mock_extract_questions, _mock_save_session, mock_get_opencode_session_id = (
            mock_plan_loop_base
        )
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
            auto_mode=True,
            plan_loop=False,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_plan_agent.return_value = (
            0,
            "Plan\n## Implementation Plan\ncontent\nPlease check my questions above.",
            None,
        )
        mock_extract_plan.return_value = "build plan"
        mock_extract_questions.return_value = ["What is X?"]
        mock_get_opencode_session_id.return_value = None

        with pytest.raises(AutoCancelledError):
            await run_plan_step(context)

        mock_run_resolve_step.assert_not_called()

    @pytest.mark.asyncio
    async def test_plan_loop_disabled_sets_session_awaiting_input(
        self,
        faker,
        mock_plan_loop_base,
        mock_run_resolve_step,
        mock_post_comment,
        mock_update_ticket_status,
        mock_update_session_step,
    ):

        mock_plan_agent, mock_extract_plan, mock_extract_questions, _mock_save_session, mock_get_opencode_session_id = (
            mock_plan_loop_base
        )
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
            auto_mode=True,
            plan_loop=False,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_plan_agent.return_value = (
            0,
            "Plan\n## Implementation Plan\ncontent\nPlease check my questions above.",
            None,
        )
        mock_extract_plan.return_value = "build plan"
        mock_extract_questions.return_value = ["What is X?"]
        mock_get_opencode_session_id.return_value = None

        with pytest.raises(AutoCancelledError):
            await run_plan_step(context)

        mock_update_session_step.assert_any_await(task_id=context.linear_task.id, step="awaiting_input")


class TestWorkflowBuild:
    @pytest.fixture
    def mock_build_agent(self):
        with patch("demetra.workflows.build.opencode_build_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_review_agents(self):
        with patch("demetra.workflows.build.run_review_agents", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_validate_agent(self):
        with patch("demetra.workflows.build.run_validate_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_lint_and_test(self):
        with patch("demetra.workflows.build.run_lint_and_test", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_user_input(self):
        with patch("demetra.workflows.build.user_input", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_bump_version(self):
        with patch("demetra.workflows.build.bump_project_version", return_value="1.15.0") as m:
            yield m

    @pytest.mark.asyncio
    async def test_run_build_step_success(
        self,
        faker,
        mock_build_agent,
        mock_run_review_agents,
        mock_run_validate_agent,
        mock_run_lint_and_test,
        mock_user_input,
        mock_bump_version,
    ):
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_build_agent.return_value = (0, "", "")
        mock_run_validate_agent.return_value = None
        mock_run_review_agents.return_value = None
        mock_run_lint_and_test.return_value = (False, None)
        mock_user_input.return_value = ("1", None)

        result = await run_build_step("test build plan", context)

        assert result is None
        mock_bump_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_build_step_feeds_missing_items_back_to_build_agent(
        self,
        faker,
        mock_build_agent,
        mock_run_review_agents,
        mock_run_validate_agent,
        mock_run_lint_and_test,
        mock_user_input,
        mock_bump_version,
    ):
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
            auto_mode=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        missing_items = "Plan step 1: Add endpoint — not implemented (no corresponding change in diff)"
        mock_build_agent.return_value = (0, "", "")
        mock_run_validate_agent.side_effect = [missing_items, None]
        mock_run_review_agents.return_value = None
        mock_run_lint_and_test.return_value = (False, None)
        mock_user_input.return_value = ("1", None)

        result = await run_build_step("test build plan", context)

        assert result is None
        assert mock_build_agent.call_count == 2
        assert mock_run_validate_agent.call_count == 2
        first_task = mock_build_agent.call_args_list[0].kwargs["task"]
        second_task = mock_build_agent.call_args_list[1].kwargs["task"]
        assert first_task == "test build plan"
        assert second_task == missing_items
        mock_run_review_agents.assert_awaited_once()
        mock_bump_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_build_step_review_skipped_until_validate_passes(
        self,
        faker,
        mock_build_agent,
        mock_run_review_agents,
        mock_run_validate_agent,
        mock_run_lint_and_test,
        mock_user_input,
        mock_bump_version,
    ):
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
            auto_mode=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_build_agent.return_value = (0, "", "")
        mock_run_validate_agent.side_effect = [
            "Plan step 1: Add endpoint — not implemented (no corresponding change in diff)",
            "Plan step 2: Wire tests — not implemented (no corresponding change in diff)",
            None,
        ]
        mock_run_review_agents.return_value = None
        mock_run_lint_and_test.return_value = (False, None)
        mock_user_input.return_value = ("1", None)

        result = await run_build_step("test build plan", context)

        assert result is None
        assert mock_build_agent.call_count == 3
        assert mock_run_validate_agent.call_count == 3
        assert mock_run_review_agents.call_count == 1
        assert mock_run_review_agents.await_count == 1

    @pytest.mark.asyncio
    async def test_run_build_step_validate_failures_do_not_exhaust_review_budget(
        self,
        faker,
        mock_build_agent,
        mock_run_review_agents,
        mock_run_validate_agent,
        mock_run_lint_and_test,
        mock_user_input,
        mock_bump_version,
    ):
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
            auto_mode=True,
            linear_task=LinearTask(
                id=str(uuid4()),
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        missing_items = "Plan step 1: Add endpoint — not implemented (no corresponding change in diff)"
        mock_build_agent.return_value = (0, "", "")
        # More validate failures than MAX_REVIEW_ATTEMPTS: the review step must
        # still run once instead of being starved by validate retries.
        mock_run_validate_agent.side_effect = [missing_items] * 11 + [None]
        mock_run_review_agents.return_value = None
        mock_run_lint_and_test.return_value = (False, None)
        mock_user_input.return_value = ("1", None)

        with (
            patch("demetra.workflows.build.MAX_BUILD_ATTEMPTS", 50),
            patch("demetra.workflows.build.MAX_REVIEW_ATTEMPTS", 10),
        ):
            result = await run_build_step("test build plan", context)

        assert result is None
        assert mock_run_validate_agent.call_count == 12
        assert mock_run_review_agents.call_count == 1
        assert mock_build_agent.call_count == 12


class TestContextCompaction:
    """Tests for check_and_compact_context in build.py."""

    @pytest.fixture
    def mock_opencode_compact_session(self):
        with patch("demetra.workflows.build.opencode_compact_session", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_opencode_session_tokens(self):
        with patch("demetra.workflows.build.get_opencode_session_tokens", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_record_session_step_history(self):
        with patch("demetra.workflows.build.record_session_step_history", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_threshold(self):
        with patch("demetra.workflows.build.CONTEXT_COMPACTION_THRESHOLD", 100_000):
            yield

    def make_context(self, faker, session_id: str | None = "ses_test123") -> Context:
        return Context(
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=Session(
                task_id="TASK-1",
                session_id=session_id,
                build_plan="plan",
                posted_to_linear=False,
                step="build",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            if session_id
            else None,
        )

    def _make_history(self, length: int | None, context_tokens: int | None = None) -> SessionHistory:
        return SessionHistory(
            id="hist_1",
            session_id="ses_test123",
            step="build",
            length=length,
            context_tokens=context_tokens,
            created_at=datetime.now().isoformat(),
        )

    @pytest.mark.asyncio
    async def test_compacts_when_context_exceeds_threshold(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
        mock_threshold,
    ):
        context = self.make_context(faker)
        mock_get_opencode_session_tokens.return_value = TokenUsage(input=100, output=50, context=150_000)
        mock_record_session_step_history.return_value = self._make_history(150_000, context_tokens=150_000)
        mock_opencode_compact_session.return_value = (0, "compacted", "")

        await check_and_compact_context(context)

        mock_opencode_compact_session.assert_awaited_once_with(
            target_path=context.worktree_path,
            session_id=context.session_id,
            env=context.project.environment,
        )

    @pytest.mark.asyncio
    async def test_logs_compaction_failure(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
        mock_threshold,
    ):
        context = self.make_context(faker)
        mock_get_opencode_session_tokens.return_value = TokenUsage(input=100, output=50, context=150_000)
        mock_record_session_step_history.return_value = self._make_history(150_000, context_tokens=150_000)
        mock_opencode_compact_session.return_value = (1, "", "error details")

        await check_and_compact_context(context)

        mock_opencode_compact_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_compact_when_below_threshold(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
        mock_threshold,
    ):
        context = self.make_context(faker)
        mock_get_opencode_session_tokens.return_value = TokenUsage(input=100, output=50, context=50_000)
        mock_record_session_step_history.return_value = self._make_history(50_000, context_tokens=50_000)

        await check_and_compact_context(context)

        mock_opencode_compact_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_compact_when_context_is_none(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
        mock_threshold,
    ):
        context = self.make_context(faker)
        mock_get_opencode_session_tokens.return_value = TokenUsage(input=100, output=50, context=None)
        mock_record_session_step_history.return_value = self._make_history(None, context_tokens=None)

        await check_and_compact_context(context)

        mock_opencode_compact_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_ops_when_session_id_is_none(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
    ):
        context = self.make_context(faker, session_id=None)

        await check_and_compact_context(context)

        mock_get_opencode_session_tokens.assert_not_called()
        mock_record_session_step_history.assert_not_called()
        mock_opencode_compact_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_step_history(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
        mock_threshold,
    ):
        context = self.make_context(faker)
        mock_get_opencode_session_tokens.return_value = TokenUsage(input=100, output=50)
        mock_record_session_step_history.return_value = self._make_history(80_000)

        await check_and_compact_context(context)

        mock_record_session_step_history.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_step_history_error(
        self,
        faker,
        mock_get_opencode_session_tokens,
        mock_opencode_compact_session,
        mock_record_session_step_history,
        mock_threshold,
    ):
        context = self.make_context(faker)
        mock_get_opencode_session_tokens.return_value = TokenUsage(input=100, output=50)
        mock_record_session_step_history.side_effect = OSError("connection refused")

        await check_and_compact_context(context)

        mock_get_opencode_session_tokens.assert_awaited_once()
        mock_record_session_step_history.assert_awaited_once()
        mock_opencode_compact_session.assert_not_called()


class TestWorkflowReview:
    @pytest.fixture
    def mock_review_agent(self):
        with patch("demetra.workflows.review.opencode_review_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_summarize_review(self):
        with patch("demetra.workflows.review.summarize_review", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_run_review_agents_returns_comments(self, faker, mock_review_agent, mock_summarize_review):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_review_agent.return_value = (0, "Raw review output from agent.", None)
        mock_summarize_review.return_value = ["Some comments here"]

        result = await run_review_agents(target_path)

        assert result and "Some comments here" in result

    @pytest.mark.asyncio
    async def test_run_review_agents_no_issue_tokens(self, faker, mock_review_agent, mock_summarize_review):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_review_agent.return_value = (0, "no issues found.", None)
        mock_summarize_review.return_value = []

        result = await run_review_agents(target_path)

        assert result is None
        mock_summarize_review.assert_awaited_once_with(review_output="", user_id=None)

    @pytest.mark.asyncio
    async def test_run_review_agents_filters_thinking_prose(self, faker, mock_review_agent, mock_summarize_review):
        target_path = Path(f"/tmp/{faker.slug()}")
        thinking_prose = (
            "Looking at the staged changes, they're all test additions and configuration updates.\n"
            "Let me run a quick lint check to verify the test code quality.\n"
            "All staged changes pass lint checks. Let me verify the tests can actually run:\n"
            "All 72 tests pass. No high-severity issues found."
        )
        mock_review_agent.return_value = (0, thinking_prose, None)
        mock_summarize_review.return_value = []

        result = await run_review_agents(target_path)

        assert result is None
        mock_summarize_review.assert_awaited_once()
        sent_to_summarizer = mock_summarize_review.call_args.kwargs["review_output"]
        for line in thinking_prose.splitlines():
            assert line in sent_to_summarizer

    @pytest.mark.asyncio
    async def test_run_review_agents_returns_none_when_summarizer_finds_nothing(
        self, faker, mock_review_agent, mock_summarize_review
    ):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_review_agent.return_value = (0, "Some prose that turns out to be just thinking.", None)
        mock_summarize_review.return_value = []

        result = await run_review_agents(target_path)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_review_agents_propagates_review_error(self, faker, mock_review_agent, mock_summarize_review):
        from demetra.library.exceptions import ReviewError

        target_path = Path(f"/tmp/{faker.slug()}")
        mock_review_agent.return_value = (0, "Some review output", None)
        mock_summarize_review.side_effect = ReviewError("Failed to summarize the review")

        with pytest.raises(ReviewError, match="Failed to summarize the review"):
            await run_review_agents(target_path)


class TestWorkflowLint:
    @pytest.fixture
    def mock_is_package_installed(self):
        with patch("demetra.workflows.lint.is_package_installed", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_ruff_format(self):
        with patch("demetra.workflows.lint.run_ruff_format", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_ruff_checks(self):
        with patch("demetra.workflows.lint.run_ruff_checks", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_run_pytests(self):
        with patch("demetra.workflows.lint.run_pytests", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture(autouse=True)
    def mock_features_enabled(self):
        with patch.dict("demetra.workflows.lint.FEATURES", {"is_ruff_enabled": True, "is_pytest_enabled": True}):
            yield

    @pytest.mark.asyncio
    async def test_run_lint_and_test_returns_errors(
        self,
        faker,
        mock_is_package_installed,
        mock_run_ruff_format,
        mock_run_ruff_checks,
    ):
        target_path = Path(f"/tmp/{faker.slug()}")

        mock_is_package_installed.return_value = True
        mock_run_ruff_checks.return_value = (1, "lint errors", None)

        result = await run_lint_and_test(target_path)

        assert result == (True, "lint errors")

    @pytest.mark.asyncio
    async def test_run_lint_and_test_no_errors(
        self,
        faker,
        mock_is_package_installed,
        mock_run_ruff_format,
        mock_run_ruff_checks,
        mock_run_pytests,
    ):
        target_path = Path(f"/tmp/{faker.slug()}")

        mock_is_package_installed.return_value = True
        mock_run_ruff_checks.return_value = (0, "", None)
        mock_run_pytests.return_value = (0, "", None)

        result = await run_lint_and_test(target_path)

        assert result == (False, None)

    @pytest.mark.asyncio
    async def test_ruff_skipped_when_feature_disabled(
        self,
        faker,
        mock_is_package_installed,
        mock_run_ruff_format,
        mock_run_ruff_checks,
        mock_run_pytests,
    ):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_is_package_installed.return_value = True
        mock_run_pytests.return_value = (0, "", "")

        with patch.dict("demetra.workflows.lint.FEATURES", {"is_ruff_enabled": False, "is_pytest_enabled": True}):
            result = await run_lint_and_test(target_path)

        assert result == (False, None)
        mock_run_ruff_format.assert_not_called()
        mock_run_ruff_checks.assert_not_called()

    @pytest.mark.asyncio
    async def test_pytest_skipped_when_feature_disabled(
        self,
        faker,
        mock_is_package_installed,
        mock_run_ruff_format,
        mock_run_ruff_checks,
        mock_run_pytests,
    ):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_is_package_installed.return_value = True
        mock_run_ruff_checks.return_value = (0, "", None)

        with patch.dict("demetra.workflows.lint.FEATURES", {"is_ruff_enabled": True, "is_pytest_enabled": False}):
            result = await run_lint_and_test(target_path)

        assert result == (False, None)
        mock_run_pytests.assert_not_called()

    @pytest.mark.asyncio
    async def test_both_features_disabled_skips_everything(
        self,
        faker,
        mock_is_package_installed,
        mock_run_ruff_format,
        mock_run_ruff_checks,
        mock_run_pytests,
    ):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_is_package_installed.return_value = True

        with patch.dict("demetra.workflows.lint.FEATURES", {"is_ruff_enabled": False, "is_pytest_enabled": False}):
            result = await run_lint_and_test(target_path)

        assert result == (False, None)
        mock_run_ruff_format.assert_not_called()
        mock_run_ruff_checks.assert_not_called()
        mock_run_pytests.assert_not_called()


class TestWorkflowCleanup:
    @pytest.fixture
    def mock_git_add_all(self):
        with patch("demetra.workflows.cleanup.git_add_all", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_git_commit(self):
        with patch("demetra.workflows.cleanup.git_commit", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_git_push(self):
        with patch("demetra.workflows.cleanup.git_push", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_create_pull_request(self):
        with patch("demetra.workflows.cleanup.create_pull_request", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_generate_pr_description(self):
        with patch("demetra.workflows.cleanup.generate_pr_description", new_callable=AsyncMock) as m:
            m.return_value = "Generated PR body"
            yield m

    @pytest.fixture
    def mock_update_session_pr_link(self):
        with patch("demetra.workflows.cleanup.update_session_pr_link", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_git_cleanup(self):
        with patch("demetra.workflows.cleanup.git_cleanup", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_linear_cleanup(self):
        with patch("demetra.workflows.cleanup.linear_cleanup", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_write_session_wiki_page(self):
        with patch("demetra.workflows.cleanup.write_session_wiki_page", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_commit_deps(
        self,
        mock_git_add_all,
        mock_git_commit,
        mock_git_push,
        mock_create_pull_request,
        mock_generate_pr_description,
        mock_write_session_wiki_page,
    ):
        return (
            mock_git_add_all,
            mock_git_commit,
            mock_git_push,
            mock_create_pull_request,
            mock_generate_pr_description,
            mock_write_session_wiki_page,
        )

    @pytest.mark.asyncio
    async def test_commit_and_push(self, faker, mock_commit_deps):
        _mock_add_all, _mock_commit, _mock_push, mock_pr, _mock_pr_body, mock_wiki = mock_commit_deps
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        _mock_add_all.return_value = True
        mock_pr.return_value = (0, "https://github.com/test/demetra/pull/1", "")

        result = await commit_and_push(context)
        assert result is True
        mock_wiki.assert_awaited_once_with(context=context, wiki_root=context.worktree_path / "wiki")
        assert _mock_add_all.await_count == 2

    @pytest.mark.asyncio
    async def test_commit_and_push_pr_failure(self, faker, mock_commit_deps):

        _mock_add_all, _mock_commit, _mock_push, mock_pr, _mock_pr_body, mock_wiki = mock_commit_deps
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        _mock_add_all.return_value = True
        mock_pr.return_value = (1, "", "gh: could not create PR")

        with pytest.raises(PullRequestError, match="could not create PR"):
            await commit_and_push(context)
        mock_wiki.assert_awaited_once_with(context=context, wiki_root=context.worktree_path / "wiki")

    @pytest.mark.asyncio
    async def test_commit_and_push_pr_description_failure_raises_pull_request_error(self, faker, mock_commit_deps):
        from demetra.library.exceptions import PrDescriptionError

        _mock_add_all, _mock_commit, _mock_push, mock_pr, mock_pr_body, mock_wiki = mock_commit_deps
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        _mock_add_all.return_value = True
        mock_pr_body.side_effect = PrDescriptionError("Failed to generate the PR description")

        with pytest.raises(PullRequestError, match="Failed to generate PR description"):
            await commit_and_push(context)

        mock_pr.assert_not_awaited()
        mock_wiki.assert_awaited_once_with(context=context, wiki_root=context.worktree_path / "wiki")

    @pytest.mark.asyncio
    async def test_commit_and_push_persists_pr_link(
        self,
        faker,
        mock_commit_deps,
        mock_update_session_pr_link,
    ):
        _mock_add_all, _mock_commit, _mock_push, mock_pr, _mock_pr_body, mock_wiki = mock_commit_deps
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_pr.return_value = (0, "https://github.com/test/demetra/pull/42\n", "")

        await commit_and_push(context)
        mock_update_session_pr_link.assert_awaited_once_with(
            task_id=context.linear_task.id,
            pr_link="https://github.com/test/demetra/pull/42",
        )
        mock_wiki.assert_awaited_once_with(context=context, wiki_root=context.worktree_path / "wiki")

    @pytest.mark.asyncio
    async def test_commit_and_push_skips_pr_link_when_url_missing(
        self,
        faker,
        mock_commit_deps,
        mock_update_session_pr_link,
    ):
        _mock_add_all, _mock_commit, _mock_push, mock_pr, _mock_pr_body, mock_wiki = mock_commit_deps
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        mock_pr.return_value = (0, "Pull request created successfully\n", "")

        await commit_and_push(context)
        mock_update_session_pr_link.assert_not_awaited()
        mock_wiki.assert_awaited_once_with(context=context, wiki_root=context.worktree_path / "wiki")

    @pytest.mark.asyncio
    async def test_commit_and_push_wiki_failure_returns_true_after_successful_push(self, faker, mock_commit_deps):
        _mock_add_all, _mock_commit, _mock_push, _mock_pr, _mock_pr_body, mock_wiki = mock_commit_deps
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        _mock_add_all.return_value = True
        _mock_pr.return_value = (0, "https://github.com/test/demetra/pull/1", "")
        mock_wiki.side_effect = OSError("disk full")

        result = await commit_and_push(context)
        assert result is True
        _mock_commit.assert_awaited_once()
        _mock_push.assert_awaited_once()
        _mock_pr.assert_awaited_once()
        assert _mock_add_all.await_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_workflow_success(self, faker, mock_git_cleanup, mock_linear_cleanup):
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
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        await cleanup_workflow(context, is_success=True, should_update_linear_status=True)

    @pytest.mark.asyncio
    async def test_cleanup_workflow_failure_with_awaiting_input(
        self,
        faker,
        mock_git_cleanup,
        mock_linear_cleanup,
    ):
        with (
            patch("demetra.workflows.cleanup.update_session_step", new_callable=AsyncMock) as mock_update_step,
            patch("demetra.workflows.cleanup.get_opencode_session_tokens", new_callable=AsyncMock),
            patch("demetra.workflows.cleanup.record_session_step_history", new_callable=AsyncMock),
        ):
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
                    priority=1,
                    created_at=datetime.now().isoformat(),
                ),
                branch_name="feature/test",
                worktree_path=Path(f"/tmp/{faker.slug()}"),
                session=Session(
                    task_id=str(uuid4()),
                    build_plan="plan",
                    posted_to_linear=False,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    step="plan",
                    session_id=str(uuid4()),
                ),
            )

            await cleanup_workflow(
                context=context,
                is_success=False,
                should_update_linear_status=True,
                failure_step="awaiting_input",
            )

            mock_update_step.assert_awaited_once_with(task_id=context.linear_task.id, step="awaiting_input")


class TestMainBumpVersion:
    @pytest.fixture
    def context(self, faker) -> Context:
        return Context(
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
                priority=1,
                created_at=datetime.now().isoformat(),
                labels=["bug"],
            ),
            branch_name=f"feature/{faker.slug()}",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=Session(
                task_id=str(uuid4()),
                build_plan="Some build plan",
                posted_to_linear=True,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                step="plan",
            ),
        )

    @pytest.mark.asyncio
    async def test_main_calls_build_step_before_commit(self, faker, context):
        with (
            patch("main.init_db", new_callable=AsyncMock),
            patch("main.print_heading", new_callable=AsyncMock),
            patch("main.setup_workflow", new_callable=AsyncMock, return_value=context),
            patch("main.update_ticket_status", new_callable=AsyncMock),
            patch("main.setup_session_logging", new_callable=AsyncMock),
            patch("main.run_plan_step", new_callable=AsyncMock, return_value=True),
            patch("main.post_comment", new_callable=AsyncMock),
            patch("main.mark_session_posted", new_callable=AsyncMock),
            patch("main.run_build_step", new_callable=AsyncMock) as mock_build,
            patch("main.commit_and_push", new_callable=AsyncMock, return_value=True),
            patch("main.cleanup_workflow", new_callable=AsyncMock),
        ):
            from main import main

            await main(project_name="demetra", auto_mode=True)
            mock_build.assert_called_once()


class TestWorkflowResearch:
    @pytest.fixture
    def mock_research_agent(self):
        with patch("demetra.workflows.research.opencode_research_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_post_comment(self):
        with patch("demetra.workflows.research.post_comment", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_get_linear_config_value(self):
        with patch("demetra.workflows.research.get_linear_config_value", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_update_ticket_status(self):
        with patch("demetra.workflows.research.update_ticket_status", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_update_session_step(self):
        with patch("demetra.workflows.research.update_session_step", new_callable=AsyncMock) as m:
            yield m

    @staticmethod
    def _make_context(faker, labels=None):
        return Context(
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
                priority=1,
                created_at=datetime.now().isoformat(),
                labels=labels or [],
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

    @pytest.mark.asyncio
    async def test_run_research_step_posts_report_and_moves_to_awaiting_input(
        self,
        faker,
        mock_research_agent,
        mock_post_comment,
        mock_get_linear_config_value,
        mock_update_ticket_status,
        mock_update_session_step,
    ):
        context = self._make_context(faker)
        report = f"{RESEARCH_HEADER_STRING}\nFindings body."
        mock_research_agent.return_value = (0, f"Preamble\n{report}", "")
        mock_post_comment.return_value = True
        mock_get_linear_config_value.return_value = "state-123"
        mock_update_ticket_status.return_value = True

        result = await run_research_step(context)

        assert result == report
        mock_post_comment.assert_awaited_once_with(task_id=context.linear_task.id, body=report)
        mock_get_linear_config_value.assert_awaited_once_with(name="awaiting_input", user_id=context.project.user_id)
        mock_update_ticket_status.assert_awaited_once_with(task_id=context.linear_task.id, state_id="state-123")
        assert mock_update_session_step.call_args.kwargs["step"] == "awaiting_input"

    @pytest.mark.asyncio
    async def test_run_research_step_retries_after_agent_failure(
        self,
        faker,
        mock_research_agent,
        mock_post_comment,
        mock_get_linear_config_value,
        mock_update_ticket_status,
        mock_update_session_step,
    ):
        context = self._make_context(faker)
        report = f"{RESEARCH_HEADER_STRING}\nRecovered."
        mock_research_agent.side_effect = [(1, "", "agent crashed"), (0, report, "")]
        mock_post_comment.return_value = True
        mock_get_linear_config_value.return_value = "state-123"
        mock_update_ticket_status.return_value = True

        result = await run_research_step(context)

        assert result == report
        assert mock_research_agent.await_count == 2

    @pytest.mark.asyncio
    async def test_run_research_step_returns_none_after_all_attempts(
        self, faker, mock_research_agent, mock_post_comment, mock_update_session_step
    ):
        context = self._make_context(faker)
        mock_research_agent.return_value = (0, "output without report header", "")

        with patch("demetra.workflows.research.MAX_RESEARCH_ATTEMPTS", 1):
            result = await run_research_step(context)

        assert result is None
        assert mock_research_agent.await_count == 1
        mock_post_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_research_step_raises_when_comment_fails(
        self, faker, mock_research_agent, mock_post_comment, mock_update_session_step
    ):
        context = self._make_context(faker)
        mock_research_agent.return_value = (0, f"{RESEARCH_HEADER_STRING}\nFindings.", "")
        mock_post_comment.return_value = False

        with pytest.raises(LinearError):
            await run_research_step(context)

    @pytest.mark.asyncio
    async def test_is_research_ticket_matches_labels_case_insensitively(self, faker):
        research_context = self._make_context(faker, labels=["Research"])
        other_context = self._make_context(faker, labels=["Bug"])

        assert is_research_ticket(context=research_context) is True
        assert is_research_ticket(context=other_context) is False
