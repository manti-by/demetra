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
                "demetra.workflows.plan.get_opencode_sessions",
                new_callable=AsyncMock,
                return_value=[],
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
                            "demetra.workflows.plan.get_opencode_session_id",
                            new_callable=AsyncMock,
                            return_value=str(uuid4()),
                        ):
                            with patch(
                                "demetra.workflows.plan.save_session",
                                new_callable=AsyncMock,
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
                "demetra.workflows.plan.get_opencode_sessions",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "demetra.workflows.plan.extract_plan",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    result = await run_plan_step(context)

        assert result is None


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
            return_value=("session_id", "Some comments here", None),
        ):
            result = await run_review_agents(target_path)

        assert result == "Some comments here"

    @pytest.mark.asyncio
    async def test_run_review_agents_no_issue_tokens(self, faker):
        target_path = Path(f"/tmp/{faker.slug()}")

        with patch(
            "demetra.workflows.review.opencode_review_agent",
            new_callable=AsyncMock,
            return_value=("session_id", "no issues found.", None),
        ):
            with patch(
                "demetra.workflows.review.cursor_review_agent",
                new_callable=AsyncMock,
                return_value=("session_id", None, None),
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
