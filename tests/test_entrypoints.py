from demetra.watcher import POLL_INTERVAL


class TestWatcher:
    def test_poll_interval_value(self):
        assert POLL_INTERVAL == 300


class TestWorker:
    def test_worker_exists(self):
        from demetra.worker import connection

        assert connection is not None
