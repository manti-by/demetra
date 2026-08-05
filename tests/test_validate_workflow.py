from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import BuildError
from demetra.workflows.validate import run_validate_agent


class TestWorkflowValidate:
    @pytest.fixture
    def mock_validate_agent(self):
        with patch("demetra.workflows.validate.opencode_validate_agent", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_full_coverage_returns_none(self, faker, mock_validate_agent):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_validate_agent.return_value = (0, "", None)

        result = await run_validate_agent(target_path, "build plan")

        assert result is None

    @pytest.mark.asyncio
    async def test_full_coverage_with_no_issue_tokens_returns_none(self, faker, mock_validate_agent):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_validate_agent.return_value = (0, "no issues found.", None)

        result = await run_validate_agent(target_path, "build plan")

        assert result is None

    @pytest.mark.asyncio
    async def test_partial_coverage_returns_missing_items(self, faker, mock_validate_agent):
        target_path = Path(f"/tmp/{faker.slug()}")
        missing = (
            "Plan step 1: Add endpoint — not implemented (no corresponding change in diff)\n"
            "Plan step 3: Wire tests — not implemented (no corresponding change in diff)"
        )
        mock_validate_agent.return_value = (0, missing, None)

        result = await run_validate_agent(target_path, "build plan")

        assert result == missing

    @pytest.mark.asyncio
    async def test_empty_diff_returns_all_items_missing(self, faker, mock_validate_agent):
        target_path = Path(f"/tmp/{faker.slug()}")
        missing = "\n".join(
            f"Plan step {i}: Step {i} — not implemented (no corresponding change in diff)" for i in range(1, 4)
        )
        mock_validate_agent.return_value = (0, missing, None)

        result = await run_validate_agent(target_path, "build plan")

        assert result == missing
        assert "Plan step 1:" in result
        assert "Plan step 3:" in result

    @pytest.mark.asyncio
    async def test_nonzero_exit_raises_build_error(self, faker, mock_validate_agent):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_validate_agent.return_value = (1, "", "agent failed")

        with pytest.raises(BuildError):
            await run_validate_agent(target_path, "build plan")

    @pytest.mark.asyncio
    async def test_passes_build_plan_and_env(self, faker, mock_validate_agent):
        target_path = Path(f"/tmp/{faker.slug()}")
        mock_validate_agent.return_value = (0, "", None)
        env = {"KEY": "val"}

        await run_validate_agent(target_path, "build plan", env=env)

        mock_validate_agent.assert_awaited_once_with(target_path=target_path, build_plan="build plan", env=env)
