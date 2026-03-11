import inspect

import pytest

from demetra.services.groq import extract_plan


class TestGroqService:
    @pytest.mark.asyncio
    async def test_extract_plan_function_exists(self):
        assert callable(extract_plan)

    @pytest.mark.asyncio
    async def test_extract_plan_signature(self):
        sig = inspect.signature(extract_plan)
        params = list(sig.parameters.keys())

        assert "plan_output" in params
        assert "task_description" in params
        assert "comments" in params
        assert sig.parameters["comments"].annotation == list[str]
