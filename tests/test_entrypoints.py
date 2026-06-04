from demetra.watcher import POLL_INTERVAL


class TestWatcher:
    def test_poll_interval_value(self):
        assert POLL_INTERVAL == 60


class TestWorker:
    def test_worker_exists(self):
        from demetra.worker import connection

        assert connection is not None


class TestMainEntrypoint:
    def test_main_argparser_accepts_plan_loop(self):
        import argparse

        from main import parser

        assert isinstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--project-name", "demetra", "--plan-loop"])
        assert args.plan_loop is True

    def test_main_argparser_plan_loop_default_false(self):
        from main import parser

        args = parser.parse_args(["--project-name", "demetra"])
        assert args.plan_loop is False

    def test_main_argparser_can_disable_plan_loop(self):
        from main import parser

        args = parser.parse_args(["--project-name", "demetra", "--no-plan-loop"])
        assert args.plan_loop is False

    def test_main_function_accepts_plan_loop_kwarg(self):
        import inspect

        from main import main

        sig = inspect.signature(main)
        assert "plan_loop" in sig.parameters
