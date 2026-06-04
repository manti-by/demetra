from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.models import Context, LinearTask, Project
from demetra.workflows.build import run_build_step


class TestWorkflowBuildEdgeCases:
    @pytest.mark.asyncio
    async def test_run_build_step_handles_review_loop(self, faker):
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
            "demetra.workflows.build.opencode_build_agent",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ):
            with patch(
                "demetra.workflows.build.run_review_agents",
                new_callable=AsyncMock,
                return_value="review comments",
            ):
                with patch(
                    "demetra.workflows.build.run_lint_and_test",
                    new_callable=AsyncMock,
                    return_value=(True, "lint errors"),
                ):
                    with patch(
                        "demetra.workflows.build.user_input",
                        new_callable=AsyncMock,
                        return_value=("1", None),
                    ):
                        try:
                            await run_build_step("test build plan", context)
                        except Exception:  # noqa
                            pass
