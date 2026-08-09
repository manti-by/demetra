from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.quality.lint import run_ruff_checks
from demetra.services.quality.test import run_pytests


@pytest.mark.asyncio
class TestWorkflowIntegration:
    @pytest.fixture
    def mock_commands(self):
        with (
            patch("demetra.services.quality.lint.run_command", new_callable=AsyncMock) as mock_precommit,
            patch("demetra.services.quality.test.run_command", new_callable=AsyncMock) as mock_test,
        ):
            yield mock_precommit, mock_test

    async def test_workflow_build_precommit_test_sequence(self, mock_commands):
        target_path = Path("/test/path")
        session_id = "test-session"
        mock_precommit, mock_test = mock_commands

        build_call_count = 0
        precommit_attempt = 0
        test_attempt = 0

        async def mock_build_agent(*args, **kwargs):
            nonlocal build_call_count
            build_call_count += 1
            return "build completed"

        def precommit_side_effect(*args, **kwargs):
            nonlocal precommit_attempt
            precommit_attempt += 1
            if precommit_attempt == 1:
                raise Exception("ty check failed on first attempt")
            return "ty check output"

        def test_side_effect(*args, **kwargs):
            nonlocal test_attempt
            test_attempt += 1
            if test_attempt == 1:
                raise Exception("pytest failed on first attempt")
            return "pytest output"

        mock_precommit.side_effect = precommit_side_effect
        mock_test.side_effect = test_side_effect

        max_retries = 3
        current_task = "Initial task"

        for _ in range(max_retries):
            await mock_build_agent(
                target_path=target_path, task=current_task, session_id=session_id, task_title="Test Task"
            )

            try:
                await run_ruff_checks(target_path=target_path)
            except Exception as e:  # noqa: BLE001
                current_task = f"Fix pre-commit issues: {e}"
                continue

            try:
                await run_pytests(target_path=target_path, session_id=session_id)
            except Exception as e:  # noqa: BLE001
                current_task = f"Fix test failures: {e}"
                continue

        assert build_call_count == 3
        assert mock_precommit.call_count == 3
        assert mock_test.call_count == 2

    async def test_workflow_success_no_retry(self, mock_commands):
        target_path = Path("/test/path")
        session_id = "test-session"
        mock_precommit, mock_test = mock_commands

        build_call_count = 0

        async def mock_build_agent(*args, **kwargs):
            nonlocal build_call_count
            build_call_count += 1
            return "build completed"

        mock_precommit.return_value = "ty check output"
        mock_test.return_value = "pytest output"

        await mock_build_agent(
            target_path=target_path, task="Initial task", session_id=session_id, task_title="Test Task"
        )

        ruff_result = await run_ruff_checks(target_path=target_path)
        test_result = await run_pytests(target_path=target_path, session_id=session_id)

        assert build_call_count == 1
        assert mock_precommit.call_count == 1
        assert mock_test.call_count == 1
        assert ruff_result == "ty check output"
        assert test_result == "pytest output"
