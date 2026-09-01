from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.models import LinearTask
from demetra.services.daemons.watcher import process_tasks
from demetra.services.runtime.project import parse_github_url
from demetra.services.runtime.tui import print_message


class TestTuiService:
    @pytest.fixture
    def mock_console(self):
        with patch("demetra.services.runtime.tui.console") as mock:
            yield mock

    @pytest.fixture
    def mock_logger(self):
        with patch("demetra.services.runtime.tui.logger") as mock:
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

    @pytest.mark.parametrize(
        "style",
        ["heading", "result", "info", "error", None],
    )
    def test_print_message_escapes_rich_markup(self, style):
        from rich.markup import escape as rich_escape

        from demetra.services.runtime.tui import console as real_console

        message = (
            '`frontend/src/sw.ts:19` — `new NavigationRoute(createHandlerBoundToURL("/static/index.html"))` '
            r"matches every navigation inside the root scope. Pass a `denylist` as the second argument, "
            r"e.g. `{ denylist: [/^\/admin/, /^\/api/, /^\/static/, /^\/media/] }`."
        )
        expected = rich_escape(message)

        with patch.object(real_console, "print") as mock_print:
            print_message(message, style=style)

            printed = [call.args[0] for call in mock_print.call_args_list if call.args]
            assert expected in printed, f"escaped message not found in {printed}"


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
            "demetra.services.daemons.watcher.get_pending_session_task_ids",
            new_callable=AsyncMock,
            return_value=[],
        ):
            yield

    @pytest.fixture
    def mock_upsert_pending_session(self):
        with patch("demetra.services.daemons.watcher.upsert_pending_session", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_update_ticket_status(self):
        with patch("demetra.services.daemons.watcher.update_ticket_status", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_get_linear_config_value(self):
        with patch("demetra.services.daemons.watcher.get_linear_config_value", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_delay_run_workflow(self):
        with patch("demetra.services.daemons.watcher.delay_run_workflow", new_callable=AsyncMock) as mock:
            yield mock

    def _task(self, faker, **kwargs):
        return LinearTask(
            id=str(uuid4()),
            identifier="MNT-123",
            title=faker.sentence(),
            description=faker.text(),
            priority=1,
            created_at=datetime.now().isoformat(),
            **kwargs,
        )

    @pytest.mark.asyncio
    async def test_process_tasks_filters_missing_project_name(self, faker, mock_get_pending_session_task_ids):
        task = self._task(faker, project_name=None)

        await process_tasks(tasks=[task])

    @pytest.mark.asyncio
    async def test_process_tasks_skips_missing_project_id(self, faker, mock_get_pending_session_task_ids):
        task = self._task(faker, project_name="demetra", project_id=None)

        await process_tasks(tasks=[task])

    @pytest.mark.asyncio
    async def test_process_tasks_moves_new_task_to_in_progress(
        self,
        faker,
        mock_get_pending_session_task_ids,
        mock_upsert_pending_session,
        mock_get_linear_config_value,
        mock_update_ticket_status,
        mock_delay_run_workflow,
    ):
        task = self._task(faker, project_name="demetra", project_id="project-1", user_id="user-1")
        mock_get_linear_config_value.return_value = "in-progress-state"

        await process_tasks(tasks=[task])

        mock_upsert_pending_session.assert_awaited_once()
        mock_get_linear_config_value.assert_awaited_once_with(name="in_progress", user_id="user-1")
        mock_update_ticket_status.assert_awaited_once_with(task_id=task.id, state_id="in-progress-state")
        mock_delay_run_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_tasks_moves_existing_pending_to_in_progress(
        self,
        faker,
        mock_get_pending_session_task_ids,
        mock_upsert_pending_session,
        mock_get_linear_config_value,
        mock_update_ticket_status,
        mock_delay_run_workflow,
    ):
        # A task already pending (e.g. bounced back to TODO after a failed run)
        # skips the session upsert but is still re-moved to in_progress so it does
        # not get stuck in TODO on re-pickup.
        task = self._task(faker, project_name="demetra", project_id="project-1", user_id="user-1")
        mock_get_linear_config_value.return_value = "in-progress-state"
        with patch("demetra.services.daemons.watcher.get_pending_session_task_ids", new_callable=AsyncMock) as mock_ids:
            mock_ids.return_value = {task.id}

            await process_tasks(tasks=[task])

        mock_upsert_pending_session.assert_not_awaited()
        mock_get_linear_config_value.assert_awaited_once_with(name="in_progress", user_id="user-1")
        mock_update_ticket_status.assert_awaited_once_with(task_id=task.id, state_id="in-progress-state")
        mock_delay_run_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_tasks_logs_and_continues_when_in_progress_state_missing(
        self,
        faker,
        mock_get_pending_session_task_ids,
        mock_upsert_pending_session,
        mock_get_linear_config_value,
        mock_update_ticket_status,
        mock_delay_run_workflow,
    ):
        task = self._task(faker, project_name="demetra", project_id="project-1", user_id="user-1")
        mock_get_linear_config_value.return_value = None

        await process_tasks(tasks=[task])

        mock_update_ticket_status.assert_not_awaited()
        mock_delay_run_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_tasks_logs_and_continues_when_update_fails(
        self,
        faker,
        mock_get_pending_session_task_ids,
        mock_upsert_pending_session,
        mock_get_linear_config_value,
        mock_update_ticket_status,
        mock_delay_run_workflow,
    ):
        task = self._task(faker, project_name="demetra", project_id="project-1", user_id="user-1")
        mock_get_linear_config_value.return_value = "in-progress-state"
        mock_update_ticket_status.return_value = False

        await process_tasks(tasks=[task])

        mock_update_ticket_status.assert_awaited_once_with(task_id=task.id, state_id="in-progress-state")
        mock_delay_run_workflow.assert_awaited_once()
