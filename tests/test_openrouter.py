import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.exceptions import PlanError, WikiError
from demetra.library.models import TokenUsage
from demetra.services.llm.openrouter import (
    _extract_usage,
    _record_llm_call,
    compose_wiki_page,
    extract_plan,
    extract_questions,
    generate_pr_description,
    process_text_with_openrouter,
    summarize_review,
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
        assert "environment" in params
        assert "user_id" not in params

    @pytest.mark.asyncio
    async def test_summarize_review_function_exists(self):
        assert callable(summarize_review)

    @pytest.mark.asyncio
    async def test_summarize_review_signature(self):
        sig = inspect.signature(summarize_review)
        params = list(sig.parameters.keys())

        assert "review_output" in params
        assert sig.return_annotation == list[str]
        assert "environment" in params
        assert "user_id" not in params

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
    async def test_summarize_review_raises_review_error_on_llm_failure(self):
        from demetra.library.exceptions import ReviewError

        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.NumberedListOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(ReviewError, match="Failed to summarize the review"):
                await summarize_review(review_output="some review output")

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
        assert "environment" in params
        assert "user_id" not in params

    @pytest.mark.asyncio
    async def test_process_text_with_openrouter_function_exists(self):
        assert callable(process_text_with_openrouter)

    @pytest.mark.asyncio
    async def test_process_text_with_openrouter_signature(self):
        sig = inspect.signature(process_text_with_openrouter)
        params = list(sig.parameters.keys())

        assert "text" in params
        assert sig.return_annotation == dict[str, str]
        assert "environment" in params
        assert "user_id" not in params

    @pytest.mark.asyncio
    async def test_process_text_returns_all_ticket_fields(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "title": "Ticket title",
                        "description": "Ticket body.",
                        "technical_requirements": "- req",
                        "acceptance_criteria": "- ac",
                        "project_name": "demetra",
                    }
                )
            )
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await process_text_with_openrouter(text="raw task text")

            assert result == {
                "title": "Ticket title",
                "description": "Ticket body.",
                "technical_requirements": "- req",
                "acceptance_criteria": "- ac",
                "project_name": "demetra",
            }

    @pytest.mark.asyncio
    async def test_process_text_falls_back_on_missing_field(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "title": "Ticket title",
                        "description": "Ticket body.",
                        "technical_requirements": "- req",
                        "acceptance_criteria": "- ac",
                    }
                )
            )
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await process_text_with_openrouter(text="raw task text")

            assert result == {
                "title": "raw task text",
                "description": "raw task text",
                "technical_requirements": "",
                "acceptance_criteria": "",
                "project_name": "",
            }

    @pytest.mark.asyncio
    async def test_process_text_falls_back_on_non_string_field(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "title": "Ticket title",
                        "description": "Ticket body.",
                        "technical_requirements": "- req",
                        "acceptance_criteria": "- ac",
                        "project_name": 123,
                    }
                )
            )
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await process_text_with_openrouter(text="raw task text")

            assert result == {
                "title": "raw task text",
                "description": "raw task text",
                "technical_requirements": "",
                "acceptance_criteria": "",
                "project_name": "",
            }

    @pytest.mark.asyncio
    async def test_process_text_falls_back_on_non_dict_output(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = MagicMock(content=json.dumps(["title", "description"]))
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await process_text_with_openrouter(text="raw task text")

            assert result == {
                "title": "raw task text",
                "description": "raw task text",
                "technical_requirements": "",
                "acceptance_criteria": "",
                "project_name": "",
            }

    @pytest.mark.asyncio
    async def test_process_text_falls_back_on_llm_failure(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await process_text_with_openrouter(text="raw task text")

            assert result == {
                "title": "raw task text",
                "description": "raw task text",
                "technical_requirements": "",
                "acceptance_criteria": "",
                "project_name": "",
            }

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
            plan_passed = mock_chain.ainvoke.call_args.kwargs["input"]["plan_output"]
            assert len(plan_passed) <= 32_000
            assert plan_passed == long_output[-32_000:]

    @pytest.mark.asyncio
    async def test_extract_plan_raises_plan_error_on_llm_failure(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(PlanError, match="Failed to summarize the build plan"):
                await extract_plan(plan_output="plan", task_description="task", comments=[])


class TestExtractQuestions:
    @pytest.mark.asyncio
    async def test_returns_empty_without_marker(self):
        with patch("demetra.services.llm.openrouter.build_llm") as mock_llm:
            result = await extract_questions(plan_output="No questions signalled here")

        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_parsed_questions(self):
        from demetra.services.agents.opencode import PLAN_HAS_QUESTIONS

        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.__or__.return_value = mock_chain
            mock_chain.ainvoke.return_value = MagicMock(content="1. What is X?\n2. How to handle Y?")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await extract_questions(plan_output=f"Plan output\n{PLAN_HAS_QUESTIONS}")

            assert result == ["What is X?", "How to handle Y?"]

    @pytest.mark.asyncio
    async def test_raises_plan_error_on_llm_failure(self):
        from demetra.services.agents.opencode import PLAN_HAS_QUESTIONS

        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.NumberedListOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.__or__.return_value = mock_chain
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(PlanError, match="Failed to extract plan questions"):
                await extract_questions(plan_output=f"Plan output\n{PLAN_HAS_QUESTIONS}")


class TestComposeWikiPage:
    VALID_BODY = (
        "## TL;DR\n\nWiki pages are LLM-authored.\n\n## Follow-ups\n\n- None\n\n## References\n\n- External: -\n"
    )

    @classmethod
    def _call_kwargs(cls) -> dict:
        return {
            "title": "MNT-147: Wiki processes",
            "page_type": "implementation",
            "ticket_text": "MNT-147: Wiki processes",
            "description": "Automate wiki maintenance.",
            "build_plan": "Build steps.",
            "diff_summary": "2 files changed.",
            "diff_excerpt": "@@ -1,0 +2,1 @@\n+x = 1\n",
            "log_tail": "log line",
            "linear_url": "https://linear.app/mnt/issue/MNT-147",
            "related": [],
        }

    @staticmethod
    def _chain(result) -> MagicMock:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = result
        mock_chain.__or__.return_value = mock_chain
        mock_prompt = MagicMock()
        mock_prompt.__or__.return_value = mock_chain
        return mock_prompt

    @classmethod
    def _capturing_chain(cls, result) -> tuple[MagicMock, AsyncMock]:
        mock_prompt = cls._chain(result)
        return mock_prompt, mock_prompt.__or__.return_value

    @pytest.mark.asyncio
    async def test_compose_wiki_page_function_exists(self):
        assert callable(compose_wiki_page)

    @pytest.mark.asyncio
    async def test_compose_wiki_page_signature(self):
        sig = inspect.signature(compose_wiki_page)
        params = list(sig.parameters.keys())
        assert set(params) == {
            "title",
            "page_type",
            "ticket_text",
            "description",
            "build_plan",
            "diff_summary",
            "diff_excerpt",
            "log_tail",
            "linear_url",
            "related",
            "task_id",
            "environment",
        }
        assert "user_id" not in params

    @pytest.mark.asyncio
    async def test_compose_wiki_page_returns_body_markdown(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt = self._chain(MagicMock(content=self.VALID_BODY))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await compose_wiki_page(**self._call_kwargs())

            assert result.startswith("## TL;DR")
            assert "LLM-authored" in result

    @pytest.mark.asyncio
    async def test_compose_wiki_page_forwards_the_diff_excerpt(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt, mock_chain = self._capturing_chain(MagicMock(content=self.VALID_BODY))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            await compose_wiki_page(**self._call_kwargs())

        assert mock_chain.ainvoke.call_args.kwargs["input"]["diff_excerpt"] == "@@ -1,0 +2,1 @@\n+x = 1\n"

    @pytest.mark.asyncio
    async def test_compose_wiki_page_renders_sibling_links_without_extension(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt, mock_chain = self._capturing_chain(MagicMock(content=self.VALID_BODY))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            call_kwargs = self._call_kwargs()
            call_kwargs["related"] = ["2026-08-01-other.md", "2026-08-02-another.md"]

            await compose_wiki_page(**call_kwargs)

        rendered = mock_chain.ainvoke.call_args.kwargs["input"]["related"]
        assert "- Related: [[2026-08-01-other]]" in rendered
        assert "- Related: [[2026-08-02-another]]" in rendered
        assert ".md" not in rendered

    @pytest.mark.asyncio
    async def test_compose_wiki_page_renders_no_siblings_as_none(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt, mock_chain = self._capturing_chain(MagicMock(content=self.VALID_BODY))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            await compose_wiki_page(**self._call_kwargs())

        assert mock_chain.ainvoke.call_args.kwargs["input"]["related"] == "- None"

    @pytest.mark.asyncio
    async def test_compose_wiki_page_raises_wiki_error_on_failure(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(WikiError, match="Failed to compose the wiki page body"):
                await compose_wiki_page(**self._call_kwargs())

    @pytest.mark.asyncio
    async def test_compose_wiki_page_raises_wiki_error_on_empty_body(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt = self._chain(MagicMock(content="   "))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(WikiError, match="empty wiki page body"):
                await compose_wiki_page(**self._call_kwargs())

    @pytest.mark.asyncio
    async def test_compose_wiki_page_raises_wiki_error_on_refusal(self):
        refusal = "I'm sorry, I can't help with that request."
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt = self._chain(MagicMock(content=refusal))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(WikiError, match="missing required sections"):
                await compose_wiki_page(**self._call_kwargs())

    @pytest.mark.asyncio
    async def test_compose_wiki_page_raises_wiki_error_when_references_are_cut_off(self):
        truncated = "## TL;DR\n\nBody.\n\n## Follow-ups\n\n- None\n"
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt = self._chain(MagicMock(content=truncated))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(WikiError, match=r"missing required sections: ## References"):
                await compose_wiki_page(**self._call_kwargs())


class TestGeneratePrDescription:
    @pytest.mark.asyncio
    async def test_raises_pr_description_error_on_llm_failure(self):
        from demetra.library.exceptions import PrDescriptionError

        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(PrDescriptionError, match="Failed to generate the PR description"):
                await generate_pr_description(task_details="Task details", build_plan="Build plan")


class TestExtractUsage:
    def test_splits_cached_and_reasoning_out_of_the_totals(self):
        message = MagicMock(
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 400,
                    "prompt_tokens_details": {"cached_tokens": 200},
                    "completion_tokens_details": {"reasoning_tokens": 100},
                }
            }
        )

        usage = _extract_usage(message=message)

        assert usage == TokenUsage(input=800, output=300, reasoning=100, cache_read=200)

    def test_keeps_totals_disjoint_on_the_usage_metadata_fallback(self):
        message = MagicMock(
            response_metadata={},
            usage_metadata={
                "input_tokens": 1000,
                "output_tokens": 400,
                "input_token_details": {"cache_read": 200},
                "output_token_details": {"reasoning": 100},
            },
        )

        usage = _extract_usage(message=message)

        assert usage == TokenUsage(input=800, output=300, reasoning=100, cache_read=200)

    def test_ignores_details_that_exceed_the_totals(self):
        message = MagicMock(
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 50},
                    "completion_tokens_details": {"reasoning_tokens": 50},
                }
            }
        )

        usage = _extract_usage(message=message)

        assert usage is not None
        assert usage.input == 0
        assert usage.output == 0

    def test_returns_none_without_usage(self):
        assert _extract_usage(message=MagicMock(response_metadata={}, usage_metadata=None)) is None


class TestRecordLLMCall:
    @pytest.mark.asyncio
    async def test_records_the_reported_usage_for_the_task(self):
        message = MagicMock(response_metadata={"token_usage": {"prompt_tokens": 300, "completion_tokens": 100}})

        with (
            patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record,
            patch("demetra.services.llm.openrouter.resolve_llm_model", return_value="openai/gpt-oss-120b"),
        ):
            await _record_llm_call(task_id="TASK-1", step="summarize_review", message=message)

        mock_record.assert_awaited_once_with(
            task_id="TASK-1",
            step="summarize_review",
            model="openai/gpt-oss-120b",
            usage=TokenUsage(input=300, output=100),
            message=None,
        )

    @pytest.mark.asyncio
    async def test_records_the_failure_reason_without_usage(self):
        with (
            patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record,
            patch("demetra.services.llm.openrouter.resolve_llm_model", return_value="openai/gpt-oss-120b"),
        ):
            await _record_llm_call(task_id="TASK-1", step="summarize_review", error="LLM unavailable")

        mock_record.assert_awaited_once_with(
            task_id="TASK-1",
            step="summarize_review",
            model="openai/gpt-oss-120b",
            usage=None,
            message="LLM unavailable",
        )

    @pytest.mark.asyncio
    async def test_records_nothing_without_a_task(self):
        with patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record:
            await _record_llm_call(task_id=None, step="summarize_review")

        mock_record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_swallows_a_history_write_failure(self):
        with (
            patch(
                "demetra.services.llm.openrouter.record_llm_call",
                new_callable=AsyncMock,
                side_effect=RuntimeError("database unavailable"),
            ),
            patch("demetra.services.llm.openrouter.resolve_llm_model", return_value="openai/gpt-oss-120b"),
        ):
            await _record_llm_call(task_id="TASK-1", step="summarize_review")


class TestOpenRouterSessionCalls:
    @staticmethod
    def _message(content: str, *, usage: dict | None = None) -> MagicMock:
        metadata = {"token_usage": usage} if usage is not None else {}
        return MagicMock(content=content, response_metadata=metadata, usage_metadata=None)

    @pytest.mark.asyncio
    async def test_extract_plan_records_the_call_with_usage(self):
        message = self._message("summarized plan", usage={"prompt_tokens": 300, "completion_tokens": 100})

        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record,
            patch("demetra.services.llm.openrouter.resolve_llm_model", return_value="openai/gpt-oss-120b"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = message
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            await extract_plan(plan_output="plan", task_description="task", comments=[], task_id="TASK-1")

        mock_record.assert_awaited_once_with(
            task_id="TASK-1",
            step="summarize_plan",
            model="openai/gpt-oss-120b",
            usage=TokenUsage(input=300, output=100),
            message=None,
        )

    @pytest.mark.asyncio
    async def test_extract_plan_skips_recording_without_a_task_id(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record,
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = self._message("summarized plan")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            await extract_plan(plan_output="plan", task_description="task", comments=[])

        mock_record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extract_plan_records_the_failure_reason(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record,
            patch("demetra.services.llm.openrouter.resolve_llm_model", return_value="openai/gpt-oss-120b"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            with pytest.raises(PlanError):
                await extract_plan(plan_output="plan", task_description="task", comments=[], task_id="TASK-1")

        mock_record.assert_awaited_once_with(
            task_id="TASK-1",
            step="summarize_plan",
            model="openai/gpt-oss-120b",
            usage=None,
            message="LLM unavailable",
        )

    @pytest.mark.asyncio
    async def test_summarize_review_records_the_call(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
            patch("demetra.services.llm.openrouter.record_llm_call", new_callable=AsyncMock) as mock_record,
            patch("demetra.services.llm.openrouter.resolve_llm_model", return_value="openai/gpt-oss-120b"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = self._message("1. real finding")
            mock_chain.__or__.return_value = mock_chain
            mock_prompt = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await summarize_review(review_output="review output", task_id="TASK-1")

        assert result == ["real finding"]
        mock_record.assert_awaited_once_with(
            task_id="TASK-1",
            step="summarize_review",
            model="openai/gpt-oss-120b",
            usage=None,
            message=None,
        )
