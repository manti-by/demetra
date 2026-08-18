import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.services.llm.openrouter import (
    extract_plan,
    generate_pr_description,
    process_text_with_openrouter,
    summarize_review,
    summarize_session,
)


class TestOpenRouterService:
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
        with patch("demetra.services.llm.openrouter.build_llm") as mock_llm:
            result = await summarize_review(review_output="")

        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_review_returns_empty_for_whitespace_input(self):
        with patch("demetra.services.llm.openrouter.build_llm") as mock_llm:
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

    @pytest.mark.asyncio
    async def test_process_text_with_openrouter_function_exists(self):
        assert callable(process_text_with_openrouter)

    @pytest.mark.asyncio
    async def test_process_text_with_openrouter_signature(self):
        sig = inspect.signature(process_text_with_openrouter)
        params = list(sig.parameters.keys())

        assert "text" in params
        assert sig.return_annotation == dict[str, str]

    @pytest.mark.asyncio
    async def test_extract_plan_truncates_long_input(self):
        long_output = "HEAD" * 20_000  # 80k chars

        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_result = AsyncMock()
            mock_result.content = "summarized plan"
            mock_chain.ainvoke.return_value = mock_result
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await extract_plan(
                plan_output=long_output,
                task_description="task",
                comments=[],
            )

            assert result == "summarized plan"
            plan_passed = mock_chain.ainvoke.call_args.args[0]["plan_output"]
            assert len(plan_passed) <= 32_000
            assert plan_passed == long_output[-32_000:]


class TestSummarizeSession:
    @pytest.mark.asyncio
    async def test_summarize_session_function_exists(self):
        assert callable(summarize_session)

    @pytest.mark.asyncio
    async def test_summarize_session_signature(self):
        sig = inspect.signature(summarize_session)
        params = list(sig.parameters.keys())
        assert "ticket_text" in params
        assert "description" in params
        assert "build_plan" in params
        assert "diff_summary" in params

    @pytest.mark.asyncio
    async def test_summarize_session_returns_tldr_and_overview(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = {"tldr": "Short TL;DR", "overview": "Body overview."}
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await summarize_session(
                ticket_text="MNT-147: Wiki processes",
                description="Automate wiki maintenance.",
                build_plan="Build steps.",
                diff_summary="2 files changed.",
            )

            assert result == {"tldr": "Short TL;DR", "overview": "Body overview."}

    @pytest.mark.asyncio
    async def test_summarize_session_returns_empty_on_failure(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await summarize_session(
                ticket_text="MNT-147: Wiki processes",
                description="Automate wiki maintenance.",
                build_plan="Build steps.",
                diff_summary="2 files changed.",
            )

            assert result == {}

    @pytest.mark.asyncio
    async def test_summarize_session_returns_empty_for_non_dict_output(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = ["tldr", "overview"]
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await summarize_session(
                ticket_text="MNT-147: Wiki processes",
                description="Automate wiki maintenance.",
                build_plan="Build steps.",
                diff_summary="2 files changed.",
            )

            assert result == {}
