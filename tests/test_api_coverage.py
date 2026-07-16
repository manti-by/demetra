from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.models import LinearTask
from demetra.services.project import parse_github_url
from demetra.services.tui import print_message
from demetra.services.watcher import process_tasks


class TestTuiService:
    @pytest.fixture
    def mock_console(self):
        with patch("demetra.services.tui.console") as mock:
            yield mock

    @pytest.fixture
    def mock_logger(self):
        with patch("demetra.services.tui.logger") as mock:
            yield mock

    def test_print_message_heading(self, faker, mock_console):

        print_message(faker.sentence(), style="heading")
        mock_console.print.assert_called()

    def test_print_message_result(self, faker, mock_console):

        print_message(faker.sentence(), style="result")
        mock_console.print.assert_called()

    def test_print_message_info(self, faker, mock_console):

        print_message(faker.sentence(), style="info")
        mock_console.print.assert_called()

    def test_print_message_error(self, faker, mock_logger):

        print_message(faker.sentence(), style="error")
        mock_logger.error.assert_called()


class TestProjectService:
    def test_parse_github_url_https(self, faker):

        url = f"https://github.com/{faker.word()}/{faker.word()}"
        result = parse_github_url(url)
        assert result is not None

    def test_parse_github_url_ssh(self, faker):

        url = f"git@github.com:{faker.word()}/{faker.word()}"
        result = parse_github_url(url)
        assert result is not None

    def test_parse_github_url_invalid(self):

        result = parse_github_url("not-a-url")
        assert result is None


class TestWatcherService:
    @pytest.fixture
    def mock_get_pending_session_task_ids(self):
        with patch(
            "demetra.services.watcher.get_pending_session_task_ids",
            new_callable=AsyncMock,
            return_value=[],
        ):
            yield

    @pytest.mark.asyncio
    async def test_process_tasks_filters_missing_project_name(self, faker, mock_get_pending_session_task_ids):

        task = LinearTask(
            id=str(uuid4()),
            identifier="MNT-123",
            title=faker.sentence(),
            description=faker.text(),
            priority=1,
            created_at=datetime.now().isoformat(),
            project_name=None,
        )

        await process_tasks(tasks=[task])

    @pytest.mark.asyncio
    async def test_process_tasks_skips_missing_project_id(self, faker, mock_get_pending_session_task_ids):

        task = LinearTask(
            id=str(uuid4()),
            identifier="MNT-123",
            title=faker.sentence(),
            description=faker.text(),
            priority=1,
            created_at=datetime.now().isoformat(),
            project_name="demetra",
            project_id=None,
        )

        await process_tasks(tasks=[task])
