import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.constants import (
    PLAN_HAS_QUESTIONS,
    PLAN_HEADER_STRING,
    PLAN_IS_READY_STRING,
    RESEARCH_HEADER_STRING,
)
from demetra.library.models import SessionEnvironment
from demetra.services.agents import harness
from demetra.settings import OPENCODE


def _claude_env(**extra_project_env) -> SessionEnvironment:
    return SessionEnvironment(project_environment={"AGENT_HARNESS": "claude", **extra_project_env}, user_environment={})


def _opencode_env() -> SessionEnvironment:
    return SessionEnvironment(project_environment={}, user_environment={})


class TestHarnessDispatch:
    @pytest.mark.asyncio
    async def test_plan_agent_dispatches_to_claude(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_plan_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_plan_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            await harness.plan_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())

            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plan_agent_dispatches_to_opencode(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_plan_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_plan_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            opencode_mock.return_value = (0, "ok", "")
            await harness.plan_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())

            opencode_mock.assert_awaited_once()
            claude_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_plan_agent_with_no_environment_defaults_to_opencode(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_plan_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_plan_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            opencode_mock.return_value = (0, "ok", "")
            await harness.plan_agent(target_path=Path("/tmp"), task="t")

            opencode_mock.assert_awaited_once()
            claude_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_build_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_build_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_build_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.build_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.build_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_validate_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_validate_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_validate_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.validate_agent(target_path=Path("/tmp"), build_plan="plan", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.validate_agent(target_path=Path("/tmp"), build_plan="plan", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_fixes_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_review_fixes_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_review_fixes_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.review_fixes_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.review_fixes_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_merge_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_merge_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.merge_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.merge_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rebase_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_rebase_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_rebase_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.rebase_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.rebase_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolve_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_resolve_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_resolve_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.resolve_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.resolve_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_agent_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_research_agent", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_research_agent", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "ok", "")
            opencode_mock.return_value = (0, "ok", "")

            await harness.research_agent(target_path=Path("/tmp"), task="t", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.research_agent(target_path=Path("/tmp"), task="t", environment=_opencode_env())
            opencode_mock.assert_awaited_once()


class TestHarnessReviewAgents:
    @pytest.mark.asyncio
    async def test_claude_review_fan_out_parses_model_and_effort(self):
        with patch(
            "demetra.services.agents.harness.claude_agents.claude_review_agent", new_callable=AsyncMock
        ) as claude_mock:
            claude_mock.return_value = (0, "ok", "")
            environment = _claude_env(CLAUDE_REVIEW_MODELS="opus:xhigh,sonnet")

            await harness.review_agents(target_path=Path("/tmp"), environment=environment)

            assert claude_mock.await_count == 2
            calls = {(c.kwargs["model"], c.kwargs["effort"]) for c in claude_mock.await_args_list}
            assert calls == {("opus", "xhigh"), ("sonnet", None)}

    @pytest.mark.asyncio
    async def test_opencode_review_fan_out_uses_settings_models(self):
        with patch(
            "demetra.services.agents.harness.opencode_agents.opencode_review_agent", new_callable=AsyncMock
        ) as opencode_mock:
            opencode_mock.return_value = (0, "ok", "")

            await harness.review_agents(target_path=Path("/tmp"), environment=_opencode_env())

            assert opencode_mock.await_count == len(OPENCODE["review_models"])
            called_models = {c.kwargs["model"] for c in opencode_mock.await_args_list}
            assert called_models == set(OPENCODE["review_models"])


class TestHarnessSessionHelpers:
    def test_new_session_id_claude_returns_uuid(self):
        session_id = harness.new_session_id(environment=_claude_env())
        assert session_id is not None
        assert str(uuid.UUID(session_id)) == session_id

    def test_new_session_id_opencode_returns_none(self):
        assert harness.new_session_id(environment=_opencode_env()) is None

    @pytest.mark.asyncio
    async def test_get_session_id_claude_returns_pregenerated_without_lookup(self):
        with patch(
            "demetra.services.agents.harness.opencode_agents.get_opencode_session_id", new_callable=AsyncMock
        ) as lookup_mock:
            result = await harness.get_session_id(
                target_path=Path("/tmp"),
                task_title="MNT-1",
                pregenerated_session_id="pre-generated",
                environment=_claude_env(),
            )

            assert result == "pre-generated"
            lookup_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_session_id_opencode_looks_up_by_title(self):
        with patch(
            "demetra.services.agents.harness.opencode_agents.get_opencode_session_id", new_callable=AsyncMock
        ) as lookup_mock:
            lookup_mock.return_value = "found-session"

            result = await harness.get_session_id(
                target_path=Path("/tmp"), task_title="MNT-1", environment=_opencode_env()
            )

            assert result == "found-session"
            lookup_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_session_tokens_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.get_claude_session_tokens", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.get_opencode_session_tokens", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            await harness.get_session_tokens(target_path=Path("/tmp"), session_id="s", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.get_session_tokens(target_path=Path("/tmp"), session_id="s", environment=_opencode_env())
            opencode_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compact_session_dispatch(self):
        with (
            patch(
                "demetra.services.agents.harness.claude_agents.claude_compact_session", new_callable=AsyncMock
            ) as claude_mock,
            patch(
                "demetra.services.agents.harness.opencode_agents.opencode_compact_session", new_callable=AsyncMock
            ) as opencode_mock,
        ):
            claude_mock.return_value = (0, "", "")
            opencode_mock.return_value = (0, "", "")

            await harness.compact_session(target_path=Path("/tmp"), session_id="s", environment=_claude_env())
            claude_mock.assert_awaited_once()
            opencode_mock.assert_not_awaited()

            await harness.compact_session(target_path=Path("/tmp"), session_id="s", environment=_opencode_env())
            opencode_mock.assert_awaited_once()


class TestHarnessExtractHelpers:
    @pytest.mark.asyncio
    async def test_extract_plan_trims_leading_text_and_trailing_marker(self):
        output = f"Preamble\n{PLAN_HEADER_STRING}\nStep 1: do it.\n{PLAN_IS_READY_STRING}"
        result = await harness.extract_plan(plan_output=output)
        assert result == f"{PLAN_HEADER_STRING}\nStep 1: do it."

    @pytest.mark.asyncio
    async def test_extract_plan_trims_questions_marker(self):
        output = f"{PLAN_HEADER_STRING}\nStep 1.\n{PLAN_HAS_QUESTIONS}"
        result = await harness.extract_plan(plan_output=output)
        assert result == f"{PLAN_HEADER_STRING}\nStep 1."

    @pytest.mark.asyncio
    async def test_extract_plan_keeps_output_without_header_or_marker(self):
        result = await harness.extract_plan(plan_output="raw plan text")
        assert result == "raw plan text"

    @pytest.mark.asyncio
    async def test_extract_research_report_trims_leading_text(self):
        output = f"Preamble\n{RESEARCH_HEADER_STRING}\nFindings."
        result = await harness.extract_research_report(research_output=output)
        assert result == f"{RESEARCH_HEADER_STRING}\nFindings."

    @pytest.mark.asyncio
    async def test_extract_research_report_keeps_output_without_header(self):
        result = await harness.extract_research_report(research_output="raw output")
        assert result == "raw output"
