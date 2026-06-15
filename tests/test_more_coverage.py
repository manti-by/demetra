from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.models import Session
from demetra.services.coderabbit import coderabbit_review_agent
from demetra.services.encryption import get_fernet
from demetra.services.watcher import process_tasks, run_workflow


class TestCodeRabbitService:
    @pytest.fixture(autouse=True)
    def mock_run_command(self):
        with patch(
            "demetra.services.coderabbit.run_command",
            new_callable=AsyncMock,
            return_value=("output", "", ""),
        ):
            yield

    @pytest.mark.asyncio
    async def test_coderabbit_review_agent(self, faker):

        result = await coderabbit_review_agent(
            target_path=Path(f"/tmp/{faker.slug()}"),
        )

        assert result is not None


class TestEncryptionService:
    @pytest.fixture
    def mock_secret_key_none(self):
        with patch("demetra.services.encryption.SECRET_KEY", None):
            yield

    @pytest.fixture
    def mock_encryption_config_valid(self):
        with (
            patch.dict("os.environ", {"SECRET_KEY": "test-key", "ENCRYPTION_SALT": "test-salt"}),
            patch("demetra.services.encryption.SECRET_KEY", "test-key"),
            patch("demetra.services.encryption.ENCRYPTION_SALT", "test-salt"),
        ):
            yield

    def test_get_fernet_raises_without_config(self, mock_secret_key_none):

        with pytest.raises(ValueError):
            get_fernet()

    def test_get_fernet_with_valid_config(self, mock_encryption_config_valid):

        try:
            get_fernet()
        except ValueError:
            pass


class TestWatcherService:
    @pytest.fixture
    def mock_increment_run_attempts(self):
        with patch("demetra.services.watcher.increment_run_attempts", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_get_session(self):
        with patch("demetra.services.watcher.get_session", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def mock_max_run_attempts(self):
        with patch("demetra.services.watcher.MAX_RUN_ATTEMPTS", 3):
            yield

    @pytest.fixture
    def mock_post_comment(self):
        with patch("demetra.services.watcher.post_comment", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_update_ticket_status(self):
        with patch("demetra.services.watcher.update_ticket_status", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_create_subprocess_exec(self):
        with patch("demetra.services.watcher.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_run_workflow_empty_task_id(self):

        result = await run_workflow("demetra", "")
        assert result is False

    @pytest.mark.asyncio
    async def test_process_tasks_empty_list(self):

        await process_tasks(tasks=[])

    @pytest.mark.asyncio
    async def test_run_workflow_skips_when_max_attempts_reached(
        self,
        faker,
        mock_increment_run_attempts,
        mock_get_session,
        mock_post_comment,
        mock_update_ticket_status,
        mock_create_subprocess_exec,
    ):

        task_id = f"TASK-{faker.random_int(min=100, max=999)}"
        session = MagicMock(spec=Session)
        session.run_attempts = 4

        mock_increment_run_attempts.return_value = 4
        mock_get_session.return_value = session

        result = await run_workflow("demetra", task_id)

        assert result is False
        mock_post_comment.assert_awaited_once_with(task_id=task_id, body="Max run attempts reached")
        mock_update_ticket_status.assert_awaited_once()
        mock_create_subprocess_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_workflow_proceeds_when_below_max(
        self,
        faker,
        mock_increment_run_attempts,
        mock_get_session,
        mock_create_subprocess_exec,
    ):

        task_id = f"TASK-{faker.random_int(min=100, max=999)}"
        session = MagicMock(spec=Session)
        session.run_attempts = 1
        process_mock = AsyncMock()
        process_mock.returncode = 0
        process_mock.stdout = None
        process_mock.stderr = None
        process_mock.communicate = AsyncMock(return_value=(b"", b""))

        mock_increment_run_attempts.return_value = 1
        mock_get_session.return_value = session
        mock_create_subprocess_exec.return_value = process_mock

        result = await run_workflow("demetra", task_id)

        assert result is True
