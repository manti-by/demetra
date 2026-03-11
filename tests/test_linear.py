from unittest.mock import AsyncMock, patch

import pytest


class TestLinearService:
    @pytest.mark.asyncio
    async def test_get_todo_issues_returns_matching_project(
        self,
        graphql_todo_issues_response_demetra: dict,
    ):
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_response_demetra
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].identifier.startswith("MNT-")

    @pytest.mark.asyncio
    async def test_get_todo_issues_filters_by_project_name(
        self,
        graphql_todo_issues_multiple_response_demetra: dict,
    ):
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_multiple_response_demetra
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 2

    @pytest.mark.asyncio
    async def test_get_linear_task_returns_first_by_priority(
        self,
        graphql_todo_issues_multiple_response_demetra: dict,
    ):
        from demetra.services.linear import get_linear_task

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_multiple_response_demetra
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                task = await get_linear_task("demetra")

        assert task is not None

    @pytest.mark.asyncio
    async def test_get_linear_task_returns_none_when_no_issues(
        self,
        graphql_empty_response: dict,
    ):
        from demetra.services.linear import get_linear_task

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_empty_response
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                task = await get_linear_task("demetra")

        assert task is None

    @pytest.mark.asyncio
    async def test_update_ticket_status_returns_true_on_success(
        self,
        graphql_update_success_response: dict,
    ):
        from demetra.services.linear import update_ticket_status

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_mutation,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_mutation.return_value = "mutation"
            mock_request.return_value = graphql_update_success_response
            result = await update_ticket_status("issue-1", "state-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_ticket_status_returns_false_on_failure(
        self,
        graphql_update_failure_response: dict,
    ):
        from demetra.services.linear import update_ticket_status

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_mutation,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_mutation.return_value = "mutation"
            mock_request.return_value = graphql_update_failure_response
            result = await update_ticket_status("issue-1", "state-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_post_comment_returns_true_on_success(
        self,
        graphql_comment_success_response: dict,
    ):
        from demetra.services.linear import post_comment

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_mutation,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_mutation.return_value = "mutation"
            mock_request.return_value = graphql_comment_success_response
            result = await post_comment("issue-1", "Test comment")

        assert result is True

    @pytest.mark.asyncio
    async def test_post_comment_returns_false_on_failure(
        self,
        graphql_comment_failure_response: dict,
    ):
        from demetra.services.linear import post_comment

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_mutation,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_mutation.return_value = "mutation"
            mock_request.return_value = graphql_comment_failure_response
            result = await post_comment("issue-1", "Test comment")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_todo_issues_includes_comments(
        self,
        graphql_todo_issues_response_with_comments: dict,
    ):
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_response_with_comments
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert len(issues[0].comments) == 2
        assert "First question" in issues[0].comments[0]
        assert "Second question" in issues[0].comments[1]

    @pytest.mark.asyncio
    async def test_get_todo_issues_empty_comments(
        self,
        graphql_todo_issues_response_demetra: dict,
    ):
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_response_demetra
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].comments == []

    @pytest.mark.asyncio
    async def test_linear_task_text_includes_comments(
        self,
        graphql_todo_issues_response_with_comments: dict,
    ):
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_response_with_comments
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues("demetra")

        task_text = issues[0].text
        assert "Comments:" in task_text
        assert "First question" in task_text
        assert "Second question" in task_text
