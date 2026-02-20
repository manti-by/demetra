import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSubprocessService:
    @pytest.mark.asyncio
    async def test_run_command_returns_combined_output(self):
        from demetra.services.subprocess import run_command

        async def capture_stream(stream, result=None):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode()
                if result is not None:
                    result.append(decoded)

        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=[b"line 1\n", b"line 2\n", b""])

        mock_stderr = AsyncMock()
        mock_stderr.readline = AsyncMock(side_effect=[b"error 1\n", b""])

        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        mock_process.stderr = mock_stderr
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create,
            patch("demetra.services.subprocess.live_stream", side_effect=capture_stream),
        ):
            mock_create.return_value = mock_process
            exit_code, stdout, stderr = await run_command(["cmd"], Path("/test"))

        assert "line 1" in stdout
        assert "line 2" in stdout
        assert exit_code == 0
        assert stderr == "error 1\n"

    @pytest.mark.asyncio
    async def test_run_command_uses_correct_cwd(self):
        from demetra.services.subprocess import run_command

        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=[b"", b""])

        mock_stderr = AsyncMock()
        mock_stderr.readline = AsyncMock(side_effect=[b"", b""])

        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        mock_process.stderr = mock_stderr
        mock_process.wait = AsyncMock(return_value=0)

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create,
            patch("demetra.services.subprocess.live_stream", new_callable=AsyncMock),
        ):
            mock_create.return_value = mock_process
            await run_command(["cmd"], Path("/custom/path"))

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["cwd"] == Path("/custom/path")

    @pytest.mark.asyncio
    async def test_run_command_pipes_stdout_stderr(self):
        from demetra.services.subprocess import run_command

        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=[b"", b""])

        mock_stderr = AsyncMock()
        mock_stderr.readline = AsyncMock(side_effect=[b"", b""])

        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        mock_process.stderr = mock_stderr
        mock_process.wait = AsyncMock(return_value=0)

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create,
            patch("demetra.services.subprocess.live_stream", new_callable=AsyncMock),
        ):
            mock_create.return_value = mock_process
            await run_command(["cmd"], Path("/test"))

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["stdout"] == asyncio.subprocess.PIPE
        assert call_kwargs["stderr"] == asyncio.subprocess.PIPE
