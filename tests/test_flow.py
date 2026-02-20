from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.flow import user_input


@pytest.mark.asyncio
async def test_user_input_valid_choice():
    """Test user input with valid choice."""
    options = [("1", "Continue"), ("2", "Stop")]

    with patch("demetra.services.flow.print_message"), patch("asyncio.get_event_loop") as mock_loop:
        mock_loop_instance = AsyncMock()
        mock_loop.return_value = mock_loop_instance
        mock_loop_instance.run_in_executor = AsyncMock(side_effect=["1", ""])

        result = await user_input(options)

        assert result[0] in ["Continue", "1"]
        assert result[1] is None


@pytest.mark.asyncio
async def test_user_input_default_choice():
    """Test user input with default choice."""
    options = [("1", "Continue"), ("2", "Stop")]

    with patch("demetra.services.flow.print_message"), patch("asyncio.get_event_loop") as mock_loop:
        mock_loop_instance = AsyncMock()
        mock_loop.return_value = mock_loop_instance
        mock_loop_instance.run_in_executor = AsyncMock(side_effect=["", ""])

        result = await user_input(options)

        assert result[0] == "Continue"
        assert result[1] is None


@pytest.mark.asyncio
async def test_user_input_comment_choice():
    """Test user input with comment choice - uses lowercase to match production check."""
    options = [("1", "Continue"), ("comment", "comment")]

    with (
        patch("demetra.services.flow.print_message"),
        patch("asyncio.get_event_loop") as mock_loop,
    ):
        mock_loop_instance = AsyncMock()
        mock_loop.return_value = mock_loop_instance
        mock_loop_instance.run_in_executor = AsyncMock(side_effect=["comment", "test comment"])

        result = await user_input(options)

        assert result[0] == "comment"
        assert result[1] == "test comment"


@pytest.mark.asyncio
async def test_user_input_invalid_then_valid():
    """Test user input with invalid then valid choice."""
    options = [("1", "Continue"), ("2", "Stop")]

    with patch("demetra.services.flow.print_message"), patch("asyncio.get_event_loop") as mock_loop:
        mock_loop_instance = AsyncMock()
        mock_loop.return_value = mock_loop_instance
        mock_loop_instance.run_in_executor = AsyncMock(side_effect=["invalid", "1", ""])

        result = await user_input(options)

        assert result[0] in ["Continue", "1"]
        assert result[1] is None
