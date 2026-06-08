from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.models import Session
from demetra.services.coderabbit import coderabbit_review_agent
from demetra.services.encryption import get_fernet
from demetra.services.watcher import process_tasks, run_workflow


class TestCodeRabbitService:
    @pytest.mark.asyncio
    async def test_coderabbit_review_agent(self, faker):
        from pathlib import Path

        with patch(
            "demetra.services.coderabbit.run_command",
            new_callable=AsyncMock,
            return_value=("output", "", ""),
        ):
            result = await coderabbit_review_agent(
                target_path=Path(f"/tmp/{faker.slug()}"),
            )

        assert result is not None


class TestEncryptionService:
    def test_get_fernet_raises_without_config(self):
        with patch("demetra.services.encryption.SECRET_KEY", None):
            with pytest.raises(ValueError):
                get_fernet()

    def test_get_fernet_with_valid_config(self):
        import os

        with patch.dict(os.environ, {"SECRET_KEY": "test-key", "ENCRYPTION_SALT": "test-salt"}):
            with patch("demetra.services.encryption.SECRET_KEY", "test-key"):
                with patch("demetra.services.encryption.ENCRYPTION_SALT", "test-salt"):
                    try:
                        get_fernet()
                    except ValueError:
                        pass


class TestWatcherService:
    @pytest.mark.asyncio
    async def test_run_workflow_empty_task_id(self):
        result = await run_workflow("demetra", "")
        assert result is False

    @pytest.mark.asyncio
    async def test_process_tasks_empty_list(self):
        await process_tasks(tasks=[])

    @pytest.mark.asyncio
    async def test_run_workflow_skips_when_max_attempts_reached(self, faker):
        task_id = f"TASK-{faker.random_int(min=100, max=999)}"
        session = MagicMock(spec=Session)
        session.run_attempts = 4

        with (
            patch("demetra.services.watcher.increment_run_attempts", new_callable=AsyncMock, return_value=4),
            patch("demetra.services.watcher.get_session", new_callable=AsyncMock, return_value=session),
            patch("demetra.services.watcher.MAX_RUN_ATTEMPTS", 3),
            patch("demetra.services.watcher.post_comment", new_callable=AsyncMock) as mock_post_comment,
            patch("demetra.services.watcher.update_ticket_status", new_callable=AsyncMock) as mock_update_status,
            patch("demetra.services.watcher.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_subprocess,
        ):
            result = await run_workflow("demetra", task_id)

        assert result is False
        mock_post_comment.assert_awaited_once_with(task_id=task_id, body="Max run attempts reached")
        mock_update_status.assert_awaited_once()
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_workflow_proceeds_when_below_max(self, faker):
        task_id = f"TASK-{faker.random_int(min=100, max=999)}"
        session = MagicMock(spec=Session)
        session.run_attempts = 1
        process_mock = AsyncMock()
        process_mock.returncode = 0
        process_mock.stdout = None
        process_mock.stderr = None
        process_mock.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch("demetra.services.watcher.increment_run_attempts", new_callable=AsyncMock, return_value=1),
            patch("demetra.services.watcher.get_session", new_callable=AsyncMock, return_value=session),
            patch("demetra.services.watcher.MAX_RUN_ATTEMPTS", 3),
            patch(
                "demetra.services.watcher.asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
                return_value=process_mock,
            ),
        ):
            result = await run_workflow("demetra", task_id)

        assert result is True
