from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.models import Context, LinearTask, Project
from demetra.workflows.build import run_build_step
from demetra.workflows.cleanup import cleanup_workflow, commit_and_push
from demetra.workflows.lint import run_lint_and_test
from demetra.workflows.plan import run_plan_step
from demetra.workflows.review import run_review_agents
from demetra.workflows.setup import setup_workflow


class TestWorkflowSetup:
    @pytest.mark.asyncio
    async def test_setup_workflow_returns_context(self, faker):
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

        with patch(
            "demetra.workflows.setup.search_projects_by_name",
            new_callable=AsyncMock,
            return_value=[project_data],
        ):
            with patch(
                "demetra.workflows.setup.get_linear_task",
                new_callable=AsyncMock,
                return_value=LinearTask(**linear_task_data),  # ty: ignore
            ):
                with patch(
                    "demetra.workflows.setup.get_session",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    with patch(
                        "demetra.workflows.setup.git_pull",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "demetra.workflows.setup.git_worktree_create",
                            new_callable=AsyncMock,
                            return_value=f"/tmp/worktree/{faker.slug()}",
                        ):
                            result = await setup_workflow("demetra", auto_mode=False)

        assert result is not None
        assert result.project.name == "demetra"

    @pytest.mark.asyncio
    async def test_setup_workflow_project_not_found(self):
        with patch(
            "demetra.workflows.setup.search_projects_by_name",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await setup_workflow("nonexistent", auto_mode=False)

        assert result is None

    @pytest.mark.asyncio
    async def test_setup_workflow_multiple_projects_found(self, faker):
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
        with patch(
            "demetra.workflows.setup.search_projects_by_name",
            new_callable=AsyncMock,
            return_value=[project_data, project_data],
        ):
            result = await setup_workflow("demetra", auto_mode=False)

        assert result is None


class TestWorkflowPlan:
    @pytest.mark.asyncio
    async def test_run_plan_step_returns_build_plan(self, faker):
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
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.plan.opencode_plan_agent",
            new_callable=AsyncMock,
            return_value=("session_id", faker.text(), None),
        ):
            with patch(
                "demetra.workflows.plan.extract_plan",
                new_callable=AsyncMock,
                return_value="build plan content",
            ):
                with patch(
                    "demetra.workflows.plan.extract_questions",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    with patch(
                        "demetra.workflows.plan.save_session",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "demetra.workflows.plan.get_opencode_session_id",
                            new_callable=AsyncMock,
                            return_value=None,
                        ):
                            result = await run_plan_step(context)

        assert result == "build plan content"

    @pytest.mark.asyncio
    async def test_run_plan_step_empty_plan_returns_none(self, faker):
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
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.plan.opencode_plan_agent",
            new_callable=AsyncMock,
            return_value=("session_id", faker.text(), None),
        ):
            with patch(
                "demetra.workflows.plan.extract_plan",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await run_plan_step(context)

        assert result is None


class TestWorkflowResolve:
    @pytest.mark.asyncio
    async def test_run_resolve_step_passes_task_and_questions(self, faker):
        from demetra.workflows.resolve import run_resolve_step

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
                priority="1",
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

        with (
            patch(
                "demetra.workflows.resolve.opencode_resolve_agent",
                new_callable=AsyncMock,
                return_value=(0, "answer text", None),
            ) as mock_agent,
            patch(
                "demetra.workflows.resolve.get_prompt",
                new_callable=AsyncMock,
                return_value=resolved_prompt,
            ) as mock_prompt,
        ):
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
    async def test_run_resolve_step_uses_new_session(self, faker):
        from demetra.workflows.resolve import run_resolve_step

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
                priority="1",
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with (
            patch(
                "demetra.workflows.resolve.opencode_resolve_agent",
                new_callable=AsyncMock,
                return_value=(0, "answers", None),
            ) as mock_agent,
            patch(
                "demetra.workflows.resolve.get_prompt",
                new_callable=AsyncMock,
                return_value="prompt text",
            ),
        ):
            await run_resolve_step(context=context, original_task="task", questions=["q?"])

        call_kwargs = mock_agent.call_args.kwargs
        assert "session_id" not in call_kwargs or call_kwargs.get("session_id") is None


class TestWorkflowPlanLoop:
    @pytest.mark.asyncio
    async def test_plan_loop_calls_resolve_and_revalidates(self, faker):
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
                priority="1",
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

        async def mock_plan_agent(*args, **kwargs):
            plan_calls.append(kwargs.get("task", ""))
            if plan_calls and "Resolved Answers" in plan_calls[-1]:
                return plan_outputs[1]
            return plan_outputs[0]

        extract_plan_results = ["build plan v1", "build plan v2"]
        extract_question_results = [["How does X work?"], []]

        with patch("demetra.workflows.plan.opencode_plan_agent", new_callable=AsyncMock, side_effect=mock_plan_agent):
            with patch(
                "demetra.workflows.plan.extract_plan",
                new_callable=AsyncMock,
                side_effect=extract_plan_results,
            ):
                with patch(
                    "demetra.workflows.plan.extract_questions",
                    new_callable=AsyncMock,
                    side_effect=extract_question_results,
                ):
                    with patch(
                        "demetra.workflows.plan.run_resolve_step",
                        new_callable=AsyncMock,
                        return_value="resolved answers",
                    ) as mock_resolve:
                        with patch(
                            "demetra.workflows.plan.save_session",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "demetra.workflows.plan.get_opencode_session_id",
                                new_callable=AsyncMock,
                                return_value=None,
                            ):
                                with patch(
                                    "demetra.workflows.plan.MAX_PLAN_ATTEMPTS",
                                    3,
                                ):
                                    result = await run_plan_step(context)

        assert result == "build plan v2"
        assert mock_resolve.call_count == 1
        assert len(plan_calls) == 2
        assert "Resolved Answers" in plan_calls[1]

    @pytest.mark.asyncio
    async def test_plan_loop_max_attempts_raises(self, faker):
        from demetra.library.exceptions import InfiniteLoopError

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
                priority="1",
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.plan.opencode_plan_agent",
            new_callable=AsyncMock,
            return_value=(0, "Plan\n## Implementation Plan\ncontent\nPlease check my questions above.", None),
        ):
            with patch(
                "demetra.workflows.plan.extract_plan",
                new_callable=AsyncMock,
                return_value="build plan",
            ):
                with patch(
                    "demetra.workflows.plan.extract_questions",
                    new_callable=AsyncMock,
                    return_value=["What is X?"],
                ):
                    with patch(
                        "demetra.workflows.plan.run_resolve_step",
                        new_callable=AsyncMock,
                        return_value="answers",
                    ) as mock_resolve:
                        with patch(
                            "demetra.workflows.plan.save_session",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "demetra.workflows.plan.get_opencode_session_id",
                                new_callable=AsyncMock,
                                return_value=None,
                            ):
                                with patch(
                                    "demetra.workflows.plan.MAX_PLAN_ATTEMPTS",
                                    2,
                                ):
                                    with pytest.raises(InfiniteLoopError):
                                        await run_plan_step(context)

        assert mock_resolve.call_count == 1

    @pytest.mark.asyncio
    async def test_plan_loop_disabled_uses_linear_auto_mode(self, faker):
        from demetra.library.exceptions import AutoCancelledError

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
                priority="1",
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.plan.opencode_plan_agent",
            new_callable=AsyncMock,
            return_value=(0, "Plan\n## Implementation Plan\ncontent\nPlease check my questions above.", None),
        ):
            with patch(
                "demetra.workflows.plan.extract_plan",
                new_callable=AsyncMock,
                return_value="build plan",
            ):
                with patch(
                    "demetra.workflows.plan.extract_questions",
                    new_callable=AsyncMock,
                    return_value=["What is X?"],
                ):
                    with patch(
                        "demetra.workflows.plan.run_resolve_step",
                        new_callable=AsyncMock,
                    ) as mock_resolve:
                        with patch(
                            "demetra.workflows.plan.post_comment",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "demetra.workflows.plan.update_ticket_status",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "demetra.workflows.plan.save_session",
                                    new_callable=AsyncMock,
                                ):
                                    with patch(
                                        "demetra.workflows.plan.get_opencode_session_id",
                                        new_callable=AsyncMock,
                                        return_value=None,
                                    ):
                                        with pytest.raises(AutoCancelledError):
                                            await run_plan_step(context)

        mock_resolve.assert_not_called()


class TestWorkflowBuild:
    @pytest.mark.asyncio
    async def test_run_build_step_success(self, faker):
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
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.build.opencode_build_agent",
            new_callable=AsyncMock,
        ):
            with patch(
                "demetra.workflows.build.run_review_agents",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with patch(
                    "demetra.workflows.build.run_lint_and_test",
                    new_callable=AsyncMock,
                    return_value=(False, None),
                ):
                    with patch(
                        "demetra.workflows.build.user_input",
                        new_callable=AsyncMock,
                        return_value=("1", None),
                    ):
                        result = await run_build_step("test build plan", context)

        assert result is None


class TestWorkflowReview:
    @pytest.mark.asyncio
    async def test_run_review_agents_returns_comments(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        with patch(
            "demetra.workflows.review.opencode_review_agent",
            new_callable=AsyncMock,
            return_value=(0, "Some comments here", None),
        ):
            result = await run_review_agents(target_path)

        assert result and "Some comments here" in result

    @pytest.mark.asyncio
    async def test_run_review_agents_no_issue_tokens(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")
        with patch(
            "demetra.workflows.review.opencode_review_agent",
            new_callable=AsyncMock,
            return_value=(0, "no issues found.", None),
        ):
            result = await run_review_agents(target_path)

        assert result is None


class TestWorkflowLint:
    @pytest.mark.asyncio
    async def test_run_lint_and_test_returns_errors(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")

        with patch(
            "demetra.workflows.lint.is_package_installed",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with patch(
                "demetra.workflows.lint.run_ruff_format",
                new_callable=AsyncMock,
            ):
                with patch(
                    "demetra.workflows.lint.run_ruff_checks",
                    new_callable=AsyncMock,
                    return_value=(1, "lint errors", None),
                ):
                    result = await run_lint_and_test(target_path)

        assert result == (True, "lint errors")

    @pytest.mark.asyncio
    async def test_run_lint_and_test_no_errors(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")

        with patch(
            "demetra.workflows.lint.is_package_installed",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with patch(
                "demetra.workflows.lint.run_ruff_format",
                new_callable=AsyncMock,
            ):
                with patch(
                    "demetra.workflows.lint.run_ruff_checks",
                    new_callable=AsyncMock,
                    return_value=(0, "", None),
                ):
                    with patch(
                        "demetra.workflows.lint.run_pytests",
                        new_callable=AsyncMock,
                        return_value=(0, "", None),
                    ):
                        result = await run_lint_and_test(target_path)

        assert result == (False, None)


class TestWorkflowCleanup:
    @pytest.mark.asyncio
    async def test_commit_and_push(self, faker):
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
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.cleanup.git_add_all",
            new_callable=AsyncMock,
        ):
            with patch(
                "demetra.workflows.cleanup.git_commit",
                new_callable=AsyncMock,
            ):
                with patch(
                    "demetra.workflows.cleanup.git_push",
                    new_callable=AsyncMock,
                ):
                    with patch(
                        "demetra.workflows.cleanup.create_pull_request",
                        new_callable=AsyncMock,
                    ):
                        await commit_and_push(context)

    @pytest.mark.asyncio
    async def test_cleanup_workflow_success(self, faker):
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
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch(
            "demetra.workflows.cleanup.git_cleanup",
            new_callable=AsyncMock,
        ):
            with patch(
                "demetra.workflows.cleanup.linear_cleanup",
                new_callable=AsyncMock,
            ):
                await cleanup_workflow(context, is_success=True, should_update_linear_status=True)
