import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDatabaseService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = Path(self.temp_db.name)
        self.patcher = patch("demetra.services.database.DB_PATH", self.db_path)
        self.patcher.start()
        from demetra.services import database

        database.init_db()
        yield
        self.patcher.stop()
        self.db_path.unlink(missing_ok=True)

    def test_create_and_read(self):
        from demetra.services.database import create_session, get_session

        record = create_session("TICKET-1", "session-123")
        assert record.task_id == "TICKET-1"
        assert record.session_id == "session-123"

        found = get_session("TICKET-1")
        assert found is not None

    def test_read_nonexistent(self):
        from demetra.services.database import get_session

        result = get_session("TICKET-999")
        assert result is None
