from unittest.mock import AsyncMock

import pytest


class TestUtilsService:
    @pytest.mark.asyncio
    async def test_live_stream_reads_lines(self):
        from demetra.services.utils import live_stream

        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b"line 1\n", b"line 2\n", b""])

        result = []
        await live_stream(mock_stream, result=result)

        assert len(result) == 2
        assert "line 1" in result[0]
        assert "line 2" in result[1]

    @pytest.mark.asyncio
    async def test_live_stream_handles_empty_stream(self):
        from demetra.services.utils import live_stream

        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b""])

        result = []
        await live_stream(mock_stream, result=result)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_live_stream_stops_on_empty_line(self):
        from demetra.services.utils import live_stream

        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b"line\n", b"", b"more data\n"])

        result = []
        await live_stream(mock_stream, result=result)

        assert len(result) == 1
        assert "line" in result[0]
