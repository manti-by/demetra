from unittest.mock import patch

import pytest

from demetra.services.runtime.template import get_template


class TestGetTemplate:
    @pytest.fixture
    def mock_base_path(self, tmp_path):
        templates_dir = tmp_path / "demetra" / "templates"
        templates_dir.mkdir(parents=True)
        with patch("demetra.services.runtime.template.BASE_PATH", tmp_path):
            yield templates_dir

    @pytest.mark.asyncio
    async def test_renders_placeholders(self, mock_base_path):
        (mock_base_path / "greeting.md").write_text("Hello, {subject}!")

        result = await get_template("greeting", subject="world")

        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_returns_raw_content_without_kwargs(self, mock_base_path):
        (mock_base_path / "greeting.md").write_text("Hello, {subject}!")

        result = await get_template("greeting")

        assert result == "Hello, {subject}!"

    @pytest.mark.asyncio
    async def test_reads_template_from_templates_directory(self, mock_base_path):
        (mock_base_path / "note.md").write_text("note body")

        result = await get_template("note")

        assert result == "note body"
