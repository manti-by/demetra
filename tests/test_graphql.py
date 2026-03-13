import pytest


class TestGraphqlService:
    @pytest.mark.asyncio
    async def test_get_todo_issues_query_returns_query_string(self):
        from demetra.services.graphql import get_query

        result = await get_query(name="get_all_issues")
        assert isinstance(result, str)
        assert "issues" in result.lower()
        assert "comments" in result.lower()
