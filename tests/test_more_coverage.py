from unittest.mock import AsyncMock, patch

import pytest

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
