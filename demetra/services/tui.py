import logging.config

import aiofiles
from rich.console import Console
from rich.text import Text

from demetra.settings import BASE_PATH, LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

console = Console()


def print_message(message: str, style: str | None = None):
    if style == "heading":
        console.print("\n\u25cf ", style="bold bright_green", end="")
        console.print(message, style="bold bright_white")
        logger.info(message)
    elif style == "result":
        console.print("→ ", style="bold bright_green", end="")
        console.print(message, style="white")
        logger.info(message)
    elif style == "info":
        console.print()
        console.print(message, style="bright_black")
        logger.info(message)
    elif style == "error":
        console.print()
        console.print(message, style="red")
        logger.error(message)
    else:
        console.print(message)
        logger.info(message)


async def print_heading():
    async with aiofiles.open(BASE_PATH / "demetra/tui/header.txt") as file:
        text = await file.read()

    text = Text(text)
    text.stylize("magenta", 0, 150)
    text.stylize("cyan", 150, 250)
    text.stylize("blue", 250, 350)

    console.print()
    console.print(text, end="")
