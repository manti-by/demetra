from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from demetra.app import app
from demetra.library.models import ChatTemplate
from demetra.services.runtime.template import list_chat_templates


class TestListChatTemplates:
    @pytest.fixture
    def templates_dir(self, tmp_path):
        directory = tmp_path / "chat"
        directory.mkdir()
        with patch("demetra.services.runtime.template.CHAT_TEMPLATES_DIR", directory):
            yield directory

    async def test_lists_templates_sorted_by_name(self, templates_dir):
        (templates_dir / "research_template.md").write_text("research body")
        (templates_dir / "feature_template.md").write_text("feature body")

        result = await list_chat_templates()

        assert [template.name for template in result] == ["feature_template", "research_template"]

    async def test_derives_label_and_reads_content(self, templates_dir):
        (templates_dir / "feature_template.md").write_text("feature body")

        result = await list_chat_templates()

        assert result == [ChatTemplate(name="feature_template", label="Feature Template", content="feature body")]

    async def test_returns_empty_list_when_directory_is_missing(self, tmp_path):
        with patch("demetra.services.runtime.template.CHAT_TEMPLATES_DIR", tmp_path / "missing"):
            result = await list_chat_templates()

        assert result == []

    async def test_skips_unreadable_files(self, templates_dir):
        (templates_dir / "feature_template.md").write_text("feature body")
        (templates_dir / "research_template.md").mkdir()

        result = await list_chat_templates()

        assert [template.name for template in result] == ["feature_template"]


class TestChatTemplatesEndpoint:
    def test_returns_shipped_templates_without_auth(self):
        response = TestClient(app).get("/api/v1/chat-templates")

        assert response.status_code == 200
        templates = response.json()
        assert [template["name"] for template in templates] == ["feature_template", "research_template"]
        assert templates[0]["label"] == "Feature Template"
        assert templates[0]["content"].startswith("## Description")
        assert templates[1]["content"].startswith("## Description")
