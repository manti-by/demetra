import asyncio
import sys
from pathlib import Path


async def live_stream(stream: asyncio.StreamReader, result: list[str] | None = None) -> None:
    while True:
        if not (line := await stream.readline()):
            break

        decoded = line.decode()
        if result is not None:
            result.append(decoded)

        sys.stdout.write(decoded)
        sys.stdout.flush()


async def is_package_installed(target_path: Path, package_name: str) -> bool:
    from demetra.services.subprocess import run_command

    _, result, _ = await run_command(
        command=["uv", "tree", "--quiet", "--package", package_name], target_path=target_path
    )
    return result != ""
