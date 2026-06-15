from unittest.mock import patch

import pytest

from demetra.services.flow import user_input


class TestUserInput:
    @pytest.fixture(autouse=True)
    def _suppress_print_message(self):
        with patch("demetra.services.flow.print_message"):
            yield

    @pytest.mark.asyncio
    async def test_user_input_valid_choice(self, monkeypatch):
        """Test user input with valid choice."""
        options = [("1", "Continue"), ("2", "Stop")]
        inputs = iter(["1", ""])

        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = await user_input(options)

        assert result[0] in ["Continue", "1"]
        assert result[1] is None

    @pytest.mark.asyncio
    async def test_user_input_default_choice(self, monkeypatch):
        """Test user input with default choice."""
        options = [("1", "Continue"), ("2", "Stop")]
        inputs = iter(["", ""])

        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = await user_input(options)

        assert result[0] == "Continue"
        assert result[1] is None

    @pytest.mark.asyncio
    async def test_user_input_comment_choice(self, monkeypatch):
        """Test user input with comment choice - uses lowercase to match production check."""
        options = [("1", "Continue"), ("comment", "comment")]
        inputs = iter(["comment", "test comment"])

        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = await user_input(options)

        assert result[0] == "comment"
        assert result[1] == "test comment"

    @pytest.mark.asyncio
    async def test_user_input_invalid_then_valid(self, monkeypatch):
        """Test user input with invalid then valid choice."""
        options = [("1", "Continue"), ("2", "Stop")]
        inputs = iter(["invalid", "1", ""])

        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = await user_input(options)

        assert result[0] in ["Continue", "1"]
        assert result[1] is None
