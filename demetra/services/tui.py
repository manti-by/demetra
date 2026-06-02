import logging.config

from rich.console import Console
from rich.text import Text

from demetra.library.header import header
from demetra.settings import LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

console = Console()


def print_message(message: str, style: str | None = None):
    if style == "heading":
        console.print("\n\u25cf ", style="bold bright_green", end="")
        console.print(message, style="bold bright_white")
    elif style == "result":
        console.print("→ ", style="bold bright_green", end="")
        console.print(message, style="white")
    elif style == "info":
        console.print()
        console.print(message, style="bright_black")
    elif style == "error":
        console.print()
        console.print(message, style="red")
        if message.strip():
            logger.error(message)
            return
    else:
        console.print(message)

    if message.strip():
        logger.info(message)


async def print_heading():
    text = Text(header)
    text.stylize("magenta", 0, 150)
    text.stylize("cyan", 150, 250)
    text.stylize("blue", 250, 350)
    console.print(text, end="")
