import pytest


class TestGraphqlService:
    @pytest.mark.asyncio
    async def test_get_todo_issues_query_returns_query_string(self):
        from demetra.services.graphql import get_todo_issues_query

        result = await get_todo_issues_query()
        assert isinstance(result, str)
        assert "query" in result.lower()
        assert "issues" in result.lower()

    @pytest.mark.asyncio
    async def test_get_todo_issues_query_returns_graphql(self):
        from demetra.services.graphql import get_todo_issues_query

        result = await get_todo_issues_query()
        assert "team" in result.lower()
        assert "state" in result.lower()
