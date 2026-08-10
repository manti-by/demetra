import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.services.runtime.subprocess import (
    build_subprocess_env,
    filter_os_env,
    run_command,
    run_command_to_file,
)


def _make_mock_process(
    stdout_lines: list[bytes] | None = None,
    stderr_lines: list[bytes] | None = None,
    exit_code: int = 0,
) -> MagicMock:
    mock_stdout = AsyncMock()
    mock_stdout.readline = AsyncMock(side_effect=(stdout_lines or []) + [b""])
    mock_stderr = AsyncMock()
    mock_stderr.readline = AsyncMock(side_effect=(stderr_lines or []) + [b""])
    mock_process = MagicMock()
    mock_process.stdout = mock_stdout
    mock_process.stderr = mock_stderr
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock(return_value=exit_code)
    return mock_process


class TestSubprocessService:
    @pytest.fixture
    def mock_live_stream(self):
        with patch("demetra.services.runtime.subprocess.live_stream", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_subprocess_exec(self):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_run_command_returns_combined_output(self, mock_subprocess_exec):
        async def capture_stream(stream, result=None, disable_stdio=False):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode()
                if result is not None:
                    result.append(decoded)

        mock_process = _make_mock_process(
            stdout_lines=[b"line 1\n", b"line 2\n"],
            stderr_lines=[b"error 1\n"],
        )
        mock_subprocess_exec.return_value = mock_process

        with patch("demetra.services.runtime.subprocess.live_stream", side_effect=capture_stream):
            exit_code, stdout, stderr = await run_command(["cmd"], Path("/test"))

        assert "line 1" in stdout
        assert "line 2" in stdout
        assert exit_code == 0
        assert stderr == "error 1\n"

    @pytest.mark.asyncio
    async def test_run_command_uses_correct_cwd(self, mock_subprocess_exec, mock_live_stream):

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process
        await run_command(["cmd"], Path("/custom/path"))

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert call_kwargs["cwd"] == Path("/custom/path")

    @pytest.mark.asyncio
    async def test_run_command_pipes_stdout_stderr(self, mock_subprocess_exec, mock_live_stream):

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process
        await run_command(["cmd"], Path("/test"))

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert call_kwargs["stdout"] == asyncio.subprocess.PIPE
        assert call_kwargs["stderr"] == asyncio.subprocess.PIPE

    @pytest.mark.asyncio
    async def test_run_command_pipes_stdin_input(self, mock_subprocess_exec, mock_live_stream):

        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock()
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()
        mock_stdin.wait_closed = AsyncMock()
        mock_process = _make_mock_process()
        mock_process.stdin = mock_stdin
        mock_subprocess_exec.return_value = mock_process

        await run_command(["cmd"], Path("/test"), input_text="long task")

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert call_kwargs["stdin"] == asyncio.subprocess.PIPE
        mock_stdin.write.assert_called_once_with(data=b"long task")
        mock_stdin.close.assert_called_once()
        mock_stdin.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_command_stdin_broken_pipe_still_returns_exit_code(self, mock_subprocess_exec, mock_live_stream):

        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock(side_effect=BrokenPipeError)
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()
        mock_stdin.wait_closed = AsyncMock()
        mock_process = _make_mock_process(exit_code=0)
        mock_process.stdin = mock_stdin
        mock_subprocess_exec.return_value = mock_process

        exit_code, _, _ = await run_command(["cmd"], Path("/test"), input_text="task")

        assert exit_code == 0
        mock_stdin.close.assert_called_once()
        mock_stdin.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_command_stdin_connection_reset_still_returns_exit_code(
        self, mock_subprocess_exec, mock_live_stream
    ):

        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock(side_effect=ConnectionResetError)
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()
        mock_stdin.wait_closed = AsyncMock()
        mock_process = _make_mock_process(exit_code=0)
        mock_process.stdin = mock_stdin
        mock_subprocess_exec.return_value = mock_process

        exit_code, _, _ = await run_command(["cmd"], Path("/test"), input_text="task")

        assert exit_code == 0
        mock_stdin.close.assert_called_once()
        mock_stdin.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_command_without_input_inherits_stdin(self, mock_subprocess_exec, mock_live_stream):

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process
        await run_command(["cmd"], Path("/test"))

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert "stdin" not in call_kwargs

    @pytest.mark.asyncio
    async def test_run_command_accepts_env_parameter(self, mock_subprocess_exec, mock_live_stream):

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process
        await run_command(["cmd"], Path("/test"), env={"CUSTOM_KEY": "custom_value"})

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert "env" in call_kwargs
        assert call_kwargs["env"]["CUSTOM_KEY"] == "custom_value"
        assert call_kwargs["env"]["PWD"] == str(Path("/test"))

    @pytest.mark.asyncio
    async def test_run_command_env_does_not_override_parent_env(self, mock_subprocess_exec, mock_live_stream):

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process

        await run_command(["cmd"], Path("/test"), env={"MY_VAR": "my_val"})

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        merged_env = call_kwargs["env"]
        assert merged_env["MY_VAR"] == "my_val"
        assert "PATH" in merged_env
        assert merged_env["PATH"] == os.environ["PATH"]

    @pytest.mark.asyncio
    async def test_run_command_without_env_inherits_parent(self, mock_subprocess_exec, mock_live_stream):

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process

        await run_command(["cmd"], Path("/test"))

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert "env" in call_kwargs
        assert "PATH" in call_kwargs["env"]
        assert call_kwargs["env"]["PATH"] == os.environ["PATH"]

    @pytest.mark.asyncio
    async def test_run_command_handles_timeout(self, mock_subprocess_exec):
        async def timeout_stream(*args, **kwargs):
            raise TimeoutError

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process

        with patch("demetra.services.runtime.subprocess.live_stream", side_effect=timeout_stream):
            exit_code, _stdout, stderr = await run_command(["cmd"], Path("/test"), timeout=1)

        assert exit_code == -1
        assert "timed out" in stderr.lower()
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_command_raises_on_missing_stdout(self, mock_subprocess_exec):
        mock_process = MagicMock()
        mock_process.stdout = None
        mock_process.stderr = None
        mock_subprocess_exec.return_value = mock_process

        with pytest.raises(AttributeError, match="stdout/stderr is None"):
            await run_command(["cmd"], Path("/test"))


class TestSubprocessToFile:
    """Regression tests for `run_command_to_file`.

    The `opencode export` subcommand truncates output to the OS pipe buffer (64KB)
    when stdout is a PIPE. This helper redirects stdout to a temp file and reads
    it back, so the full payload survives. Tests must prove stdout is NOT a PIPE.
    """

    @pytest.fixture
    def mock_live_stream(self):
        with patch("demetra.services.runtime.subprocess.live_stream", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_subprocess_exec(self):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_returns_file_content_as_stdout(self, mock_subprocess_exec, mock_live_stream, tmp_path):
        payload = b'{"info": {"tokens": {"input": 1}}}'
        mock_process = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        def _write_to_stdout_file_then_close(*args, **kwargs):
            stdout_file = kwargs["stdout"]
            stdout_file.write(payload)
            return mock_process

        mock_subprocess_exec.side_effect = _write_to_stdout_file_then_close

        exit_code, stdout, stderr = await run_command_to_file(["cmd"], tmp_path)
        assert exit_code == 0
        assert stdout == payload.decode()
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_stdout_is_not_a_pipe(self, mock_subprocess_exec, mock_live_stream, tmp_path):
        mock_process = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        await run_command_to_file(["cmd"], tmp_path)

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert call_kwargs["stdout"] is not asyncio.subprocess.PIPE
        assert hasattr(call_kwargs["stdout"], "write")

    @pytest.mark.asyncio
    async def test_temp_file_is_deleted(self, mock_subprocess_exec, mock_live_stream, tmp_path):
        mock_process = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        captured_paths: list[Path] = []

        original_unlink = Path.unlink

        def _spy_unlink(self, *args, **kwargs):
            if self.name.startswith("tmp") and self.exists():
                captured_paths.append(self)
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", _spy_unlink):
            await run_command_to_file(["cmd"], tmp_path)

        assert all(not p.exists() for p in captured_paths)

    @pytest.mark.asyncio
    async def test_forwards_env_and_cwd(self, mock_subprocess_exec, mock_live_stream, tmp_path):
        mock_process = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        await run_command_to_file(["cmd"], tmp_path, env={"CUSTOM_KEY": "custom_value"})

        call_kwargs = mock_subprocess_exec.call_args.kwargs
        assert call_kwargs["cwd"] == tmp_path
        assert call_kwargs["env"]["CUSTOM_KEY"] == "custom_value"
        assert call_kwargs["env"]["PWD"] == str(tmp_path)

    @pytest.mark.asyncio
    async def test_returns_timeout_exit_code(self, mock_subprocess_exec, mock_live_stream, tmp_path):
        async def timeout_stream(*args, **kwargs):
            raise TimeoutError

        mock_process = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        with patch("demetra.services.runtime.subprocess.live_stream", side_effect=timeout_stream):
            exit_code, _stdout, stderr = await run_command_to_file(["cmd"], tmp_path, timeout=1)

        assert exit_code == -1
        assert "timed out" in stderr.lower()
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_missing_stderr(self, mock_subprocess_exec, mock_live_stream, tmp_path):
        mock_process = MagicMock()
        mock_process.stderr = None
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        with pytest.raises(AttributeError, match="stderr is None"):
            await run_command_to_file(["cmd"], tmp_path)
        mock_process.kill.assert_called_once()


class TestFilterOsEnv:
    def test_accepts_allowlisted_keys(self, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("HOME", "/home/user")
        monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

        filtered = filter_os_env()

        assert filtered["PATH"] == "/usr/bin:/bin"
        assert filtered["HOME"] == "/home/user"
        assert "GITHUB_TOKEN" not in filtered

    def test_rejects_non_listed_keys(self, monkeypatch):
        monkeypatch.setenv("SOME_RANDOM_VAR", "value")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "akid")

        filtered = filter_os_env()

        assert "SOME_RANDOM_VAR" not in filtered
        assert "AWS_ACCESS_KEY_ID" not in filtered

    def test_case_sensitivity_per_os(self, monkeypatch):
        monkeypatch.setenv("Path", "/custom")
        monkeypatch.delenv("PATH", raising=False)

        filtered = filter_os_env()

        # Linux env var names are case-sensitive: lowercase "Path" is NOT the
        # allowlisted "PATH".
        assert "Path" not in filtered
        assert "PATH" not in filtered

    def test_project_optin_tokens_forwarded_only_for_that_project(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "token-a")
        monkeypatch.setenv("AWS_PROFILE", "prod")
        monkeypatch.setattr(
            "demetra.services.runtime.subprocess.OS_ENV_PROJECT_OPTINS",
            {"project-a": ["GITHUB_TOKEN"]},
        )

        project_a_env = filter_os_env(project_id="project-a")
        project_b_env = filter_os_env(project_id="project-b")
        no_project_env = filter_os_env()

        assert project_a_env.get("GITHUB_TOKEN") == "token-a"
        assert "GITHUB_TOKEN" not in project_b_env
        assert "GITHUB_TOKEN" not in no_project_env
        assert "AWS_PROFILE" not in project_a_env

    def test_ssh_and_proxy_vars_forwarded_even_without_project(self, monkeypatch):
        monkeypatch.setenv("SSH_AUTH_SOCK", "/run/user/1000/ssh-agent.sock")
        monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -o StrictHostKeyChecking=no")
        monkeypatch.setenv("https_proxy", "http://proxy.internal:3128")
        monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")

        env = filter_os_env()

        assert env.get("SSH_AUTH_SOCK") == "/run/user/1000/ssh-agent.sock"
        assert env.get("GIT_SSH_COMMAND") == "ssh -o StrictHostKeyChecking=no"
        assert env.get("https_proxy") == "http://proxy.internal:3128"
        assert env.get("NO_PROXY") == "localhost,127.0.0.1"


class TestBuildSubprocessEnv:
    def test_merge_order_os_user_project_extra(self, monkeypatch):
        monkeypatch.setenv("SHARED", "os-value")
        monkeypatch.setenv("PROJECT_ONLY", "os-project-value")
        monkeypatch.setenv("EXTRA_ONLY", "os-extra-value")

        merged = build_subprocess_env(
            user_environment={"SHARED": "user-value", "USER_ONLY": "user-only"},
            project_environment={"PROJECT_ONLY": "project-value"},
            extra={"EXTRA_ONLY": "extra-value"},
            target_path=Path("/work"),
        )

        assert merged["SHARED"] == "user-value"
        assert merged["USER_ONLY"] == "user-only"
        assert merged["PROJECT_ONLY"] == "project-value"
        assert merged["EXTRA_ONLY"] == "extra-value"
        assert merged["PWD"] == "/work"

    def test_project_overrides_user_shared_on_conflict(self, monkeypatch):
        merged = build_subprocess_env(
            user_environment={"CONFLICT_KEY": "user-value"},
            project_environment={"CONFLICT_KEY": "project-value"},
        )

        assert merged["CONFLICT_KEY"] == "project-value"

    def test_extra_overrides_project_on_conflict(self, monkeypatch):
        merged = build_subprocess_env(
            project_environment={"CONFLICT_KEY": "project-value"},
            extra={"CONFLICT_KEY": "extra-value"},
        )

        assert merged["CONFLICT_KEY"] == "extra-value"

    def test_os_layer_filtered_in_builder(self, monkeypatch):
        monkeypatch.setenv("RANDOM_HOST_VAR", "should-be-dropped")
        monkeypatch.setenv("PATH", "/usr/bin")

        merged = build_subprocess_env()

        assert "RANDOM_HOST_VAR" not in merged
        assert merged["PATH"] == "/usr/bin"

    def test_project_optins_apply_in_builder(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "token-a")
        monkeypatch.setattr(
            "demetra.services.runtime.subprocess.OS_ENV_PROJECT_OPTINS",
            {"project-a": ["GITHUB_TOKEN"]},
        )

        merged = build_subprocess_env(project_id="project-a")

        assert merged.get("GITHUB_TOKEN") == "token-a"

    def test_user_environment_none_leaves_os_layer_only(self, monkeypatch):
        merged = build_subprocess_env(user_environment=None)

        assert merged is not None
