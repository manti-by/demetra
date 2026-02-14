import asyncio
import sys


async def live_stream(stream: asyncio.StreamReader, result: list[str] | None = None) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break

        decoded = line.decode()
        if result is not None:
            result.append(decoded)

        sys.stdout.write(decoded)
        sys.stdout.flush()
