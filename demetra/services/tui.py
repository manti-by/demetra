import logging.config

from rich.console import Console
from rich.markup import escape
from rich.text import Text

from demetra.library.header import header
from demetra.settings import LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

console = Console()


def print_message(message: str, style: str | None = None):
    """Print a message to the console with a style, mirroring it to the log.

    Supported styles are ``heading``, ``result``, ``info``, ``error`` and the
    default unstyled text.

    Args:
        message: The message text to print.
        style: Optional display style name.
    """
    safe = escape(message) if message else ""
    if style == "heading":
        console.print("\n\u25cf ", style="bold bright_green", end="")
        console.print(safe, style="bold bright_white")
    elif style == "result":
        console.print("→ ", style="bold bright_green", end="")
        console.print(safe, style="white")
    elif style == "info":
        console.print()
        console.print(safe, style="bright_black")
    elif style == "error":
        console.print()
        console.print(safe, style="red")
        if message.strip():
            logger.error(message)
            return
    else:
        console.print(safe)

    if message.strip():
        logger.info(message)


async def print_heading():
    """Print the styled application header banner to the console."""
    text = Text(header)
    text.stylize("magenta", 0, 150)
    text.stylize("cyan", 150, 250)
    text.stylize("blue", 250, 350)
    console.print(text, end="")
