import inspect
from unittest.mock import patch

import pytest

from demetra.services.groq import extract_plan, generate_pr_description, summarize_review


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

    @pytest.mark.asyncio
    async def test_summarize_review_function_exists(self):
        assert callable(summarize_review)

    @pytest.mark.asyncio
    async def test_summarize_review_signature(self):
        sig = inspect.signature(summarize_review)
        params = list(sig.parameters.keys())

        assert "review_output" in params
        assert sig.return_annotation == list[str]

    @pytest.mark.asyncio
    async def test_summarize_review_returns_empty_for_empty_input(self):
        with patch("demetra.services.groq.ChatGroq") as mock_llm:
            result = await summarize_review(review_output="")

        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_review_returns_empty_for_whitespace_input(self):
        with patch("demetra.services.groq.ChatGroq") as mock_llm:
            result = await summarize_review(review_output="   \n\t  ")

        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_pr_description_function_exists(self):
        assert callable(generate_pr_description)

    @pytest.mark.asyncio
    async def test_generate_pr_description_signature(self):
        sig = inspect.signature(generate_pr_description)
        params = list(sig.parameters.keys())

        assert "task_details" in params
        assert "build_plan" in params
        assert sig.return_annotation is str
        assert sig.parameters["build_plan"].default is None
