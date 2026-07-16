import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.services.subprocess import run_command, run_command_to_file


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

    @pytest.mark.asyncio
    async def test_run_command_handles_timeout(self, mock_subprocess_exec):
        async def hanging_stream(*args, **kwargs):
            await asyncio.sleep(3600)

        mock_process = _make_mock_process()
        mock_subprocess_exec.return_value = mock_process

        with patch("demetra.services.subprocess.live_stream", side_effect=hanging_stream):
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
        with patch("demetra.services.subprocess.live_stream", new_callable=AsyncMock) as mock:
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
        async def hanging_stream(*args, **kwargs):
            await asyncio.sleep(3600)

        mock_process = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_subprocess_exec.return_value = mock_process

        with patch("demetra.services.subprocess.live_stream", side_effect=hanging_stream):
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
