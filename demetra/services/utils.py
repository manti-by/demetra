import asyncio
import sys
from pathlib import Path

from demetra.settings import LINEAR_CORUSCANT_PROJECT_ID, LINEAR_DEMETRA_PROJECT_ID, LINEAR_ODIN_PROJECT_ID


async def live_stream(
    stream: asyncio.StreamReader, result: list[str] | None = None, disable_stdio: bool = False
) -> None:
    while True:
        if not (line := await stream.readline()):
            break

        decoded = line.decode()
        if result is not None:
            result.append(decoded)

        if not disable_stdio:
            sys.stdout.write(decoded)
            sys.stdout.flush()


async def is_package_installed(target_path: Path, package_name: str) -> bool:
    from demetra.services.subprocess import run_command

    _, result, _ = await run_command(
        command=["uv", "tree", "--quiet", "--package", package_name],
        target_path=target_path,
        disable_stdio=True,
    )
    return result != ""


async def get_project_id_by_name(name: str) -> str | None:
    return {
        "odin": LINEAR_ODIN_PROJECT_ID,
        "demetra": LINEAR_DEMETRA_PROJECT_ID,
        "coruscant": LINEAR_CORUSCANT_PROJECT_ID,
    }.get(name)
