import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from demetra.services.precommit import precommit_agent
from demetra.services.test import test_agent


@pytest.mark.asyncio
async def test_workflow_build_precommit_test_sequence():
    """Test the complete sequence: build -> precommit -> test with retry logic."""
    target_path = Path("/test/path")
    session_id = "test-session"

    # Simulate the workflow sequence
    build_call_count = 0

    def mock_build_agent(*args, **kwargs):
        nonlocal build_call_count
        build_call_count += 1
        return "build completed"

    with (
        patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_precommit,
        patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_test,
    ):
        # First attempt: precommit fails
        def precommit_side_effect(*args, **kwargs):
            if build_call_count == 1:
                raise Exception("ty check failed on first attempt")
            else:
                return "ty check output"  # Success on retry

        def test_side_effect(*args, **kwargs):
            if build_call_count == 1:
                raise Exception("pytest failed on first attempt")
            else:
                return "pytest output"  # Success on retry

        mock_precommit.side_effect = precommit_side_effect
        mock_test.side_effect = test_side_effect

        # Simulate the retry logic from main.py
        max_retries = 3
        current_task = "Initial task"

        for attempt in range(max_retries):
            # Build agent (mocked)
            build_result = await mock_build_agent(
                target_path=target_path, task=current_task, session_id=session_id, task_title="Test Task"
            )

            # Precommit check
            try:
                await precommit_agent(target_path=target_path, session_id=session_id)
                break  # Success
            except RuntimeError as e:
                current_task = f"Fix pre-commit issues: {e}"
                continue

            # Test check (only runs if precommit succeeds)
            try:
                await test_agent(target_path=target_path, session_id=session_id)
                break  # Success
            except RuntimeError as e:
                current_task = f"Fix test failures: {e}"
                continue

        # Verify retry logic worked
        assert build_call_count == 2  # Should have retried once
        assert mock_precommit.call_count >= 2  # Called multiple times
        assert mock_test.call_count >= 1  # Called at least once


@pytest.mark.asyncio
async def test_workflow_success_no_retry():
    """Test workflow succeeds on first attempt without retry."""
    target_path = Path("/test/path")
    session_id = "test-session"

    build_call_count = 0

    def mock_build_agent(*args, **kwargs):
        nonlocal build_call_count
        build_call_count += 1
        return "build completed"

    with (
        patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_precommit,
        patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_test,
    ):
        # Mock successful execution on first attempt
        mock_precommit.side_effect = ["ty check output", "pre-commit run output"]
        mock_test.return_value = "pytest output"

        # Simulate workflow
        build_result = await mock_build_agent(
            target_path=target_path, task="Initial task", session_id=session_id, task_title="Test Task"
        )

        # Precommit check (should succeed)
        precommit_result = await precommit_agent(target_path=target_path, session_id=session_id)

        # Test check (should succeed)
        test_result = await test_agent(target_path=target_path, session_id=session_id)

        # Verify no retry was needed
        assert build_call_count == 1
        assert mock_precommit.call_count == 2  # ty check + pre-commit run
        assert mock_test.call_count == 1

        assert "ty check passed" in precommit_result
        assert test_result == "pytest output"
