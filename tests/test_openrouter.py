import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.exceptions import PlanError, WikiError
from demetra.services.llm.openrouter import (
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
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = {
                "title": "Ticket title",
                "description": "Ticket body.",
                "technical_requirements": "- req",
                "acceptance_criteria": "- ac",
                "project_name": "demetra",
            }
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
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = {
                "title": "Ticket title",
                "description": "Ticket body.",
                "technical_requirements": "- req",
                "acceptance_criteria": "- ac",
            }
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
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = {
                "title": "Ticket title",
                "description": "Ticket body.",
                "technical_requirements": "- req",
                "acceptance_criteria": "- ac",
                "project_name": 123,
            }
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
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = ["title", "description"]
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
            patch("demetra.services.llm.openrouter.JsonOutputParser"),
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
            patch("demetra.services.llm.openrouter.NumberedListOutputParser"),
        ):
            mock_chain = AsyncMock()
            mock_chain.__or__.return_value = mock_chain
            mock_chain.ainvoke.return_value = ["What is X?", "How to handle Y?"]
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
            "log_tail",
            "linear_url",
            "related",
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
            mock_prompt = self._chain(MagicMock(content="## TL;DR\n\nWiki pages are LLM-authored.\n"))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            result = await compose_wiki_page(
                title="MNT-147: Wiki processes",
                page_type="implementation",
                ticket_text="MNT-147: Wiki processes",
                description="Automate wiki maintenance.",
                build_plan="Build steps.",
                diff_summary="2 files changed.",
                log_tail="log line",
                linear_url="https://linear.app/mnt/issue/MNT-147",
                related=[],
            )

            assert result.startswith("## TL;DR")
            assert "LLM-authored" in result

    @pytest.mark.asyncio
    async def test_compose_wiki_page_renders_sibling_links_without_extension(self):
        with (
            patch("demetra.services.llm.openrouter.build_llm") as mock_llm,
            patch("demetra.services.llm.openrouter.ChatPromptTemplate") as mock_template,
            patch("demetra.services.llm.openrouter.get_prompt", new_callable=AsyncMock, return_value="system prompt"),
        ):
            mock_prompt, mock_chain = self._capturing_chain(MagicMock(content="## TL;DR\n\nBody.\n"))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            await compose_wiki_page(
                title="MNT-147: Wiki processes",
                page_type="implementation",
                ticket_text="MNT-147: Wiki processes",
                description="Automate wiki maintenance.",
                build_plan="Build steps.",
                diff_summary="2 files changed.",
                log_tail="log line",
                linear_url="https://linear.app/mnt/issue/MNT-147",
                related=["2026-08-01-other.md", "2026-08-02-another.md"],
            )

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
            mock_prompt, mock_chain = self._capturing_chain(MagicMock(content="## TL;DR\n\nBody.\n"))
            mock_template.from_messages.return_value = mock_prompt
            mock_llm.return_value = AsyncMock()

            await compose_wiki_page(
                title="MNT-147: Wiki processes",
                page_type="implementation",
                ticket_text="MNT-147: Wiki processes",
                description="Automate wiki maintenance.",
                build_plan="Build steps.",
                diff_summary="2 files changed.",
                log_tail="log line",
                linear_url="https://linear.app/mnt/issue/MNT-147",
                related=[],
            )

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
                await compose_wiki_page(
                    title="MNT-147: Wiki processes",
                    page_type="implementation",
                    ticket_text="MNT-147: Wiki processes",
                    description="Automate wiki maintenance.",
                    build_plan="Build steps.",
                    diff_summary="2 files changed.",
                    log_tail="log line",
                    linear_url="https://linear.app/mnt/issue/MNT-147",
                    related=[],
                )

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
                await compose_wiki_page(
                    title="MNT-147: Wiki processes",
                    page_type="implementation",
                    ticket_text="MNT-147: Wiki processes",
                    description="Automate wiki maintenance.",
                    build_plan="Build steps.",
                    diff_summary="2 files changed.",
                    log_tail="log line",
                    linear_url="https://linear.app/mnt/issue/MNT-147",
                    related=[],
                )


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
