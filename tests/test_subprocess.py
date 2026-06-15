import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.services.subprocess import run_command


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
        with patch("demetra.services.subprocess.live_stream", new_callable=AsyncMock) as mock:
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

        with patch("demetra.services.subprocess.live_stream", side_effect=capture_stream):
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
