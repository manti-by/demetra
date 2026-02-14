from unittest.mock import AsyncMock, patch

import pytest


class TestLinearService:
    @pytest.mark.asyncio
    async def test_get_todo_issues_returns_matching_project(self):
        from demetra.services.linear import get_todo_issues

        mock_data = {
            "data": {
                "team": {
                    "states": {
                        "nodes": [
                            {
                                "name": "Todo",
                                "issues": {
                                    "nodes": [
                                        {
                                            "id": "issue-1",
                                            "identifier": "DEMETRA-1",
                                            "title": "Test Issue",
                                            "description": "Description",
                                            "priority": 1,
                                            "createdAt": "2024-01-01",
                                            "branchName": "feature/test",
                                            "project": {"name": "demetra"},
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        }

        with (
            patch("demetra.services.linear.get_todo_issues_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].identifier == "DEMETRA-1"
        assert issues[0].title == "Test Issue"

    @pytest.mark.asyncio
    async def test_get_todo_issues_filters_by_project_name(self):
        from demetra.services.linear import get_todo_issues

        mock_data = {
            "data": {
                "team": {
                    "states": {
                        "nodes": [
                            {
                                "name": "Todo",
                                "issues": {
                                    "nodes": [
                                        {
                                            "id": "issue-1",
                                            "identifier": "DEMETRA-1",
                                            "title": "Issue 1",
                                            "description": "",
                                            "priority": 1,
                                            "createdAt": "2024-01-01",
                                            "branchName": "feature/test",
                                            "project": {"name": "demetra"},
                                        },
                                        {
                                            "id": "issue-2",
                                            "identifier": "DEMETRA-2",
                                            "title": "Issue 2",
                                            "description": "",
                                            "priority": 1,
                                            "createdAt": "2024-01-01",
                                            "branchName": "feature/test2",
                                            "project": {"name": "other"},
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        }

        with (
            patch("demetra.services.linear.get_todo_issues_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].identifier == "DEMETRA-1"

    @pytest.mark.asyncio
    async def test_get_linear_task_returns_first_by_priority(self):
        from demetra.services.linear import get_linear_task

        mock_data = {
            "data": {
                "team": {
                    "states": {
                        "nodes": [
                            {
                                "name": "Todo",
                                "issues": {
                                    "nodes": [
                                        {
                                            "id": "issue-1",
                                            "identifier": "DEMETRA-2",
                                            "title": "Low Priority",
                                            "description": "",
                                            "priority": 4,
                                            "createdAt": "2024-01-02",
                                            "branchName": "feature/low",
                                            "project": {"name": "demetra"},
                                        },
                                        {
                                            "id": "issue-2",
                                            "identifier": "DEMETRA-1",
                                            "title": "High Priority",
                                            "description": "",
                                            "priority": 1,
                                            "createdAt": "2024-01-01",
                                            "branchName": "feature/high",
                                            "project": {"name": "demetra"},
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        }

        with (
            patch("demetra.services.linear.get_todo_issues_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                task = await get_linear_task("demetra")

        assert task is not None
        assert task.identifier == "DEMETRA-1"

    @pytest.mark.asyncio
    async def test_get_linear_task_returns_none_when_no_issues(self):
        from demetra.services.linear import get_linear_task

        mock_data = {"data": {"team": {"states": {"nodes": []}}}}

        with (
            patch("demetra.services.linear.get_todo_issues_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                task = await get_linear_task("demetra")

        assert task is None
