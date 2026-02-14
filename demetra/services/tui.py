import aiofiles
from rich.console import Console
from rich.text import Text

from demetra.settings import BASE_PATH


console = Console()


def print_message(message: str, style: str | None = None):
    if style == "heading":
        console.print("\n\u25cf ", style="bold bright_green", end="")
        console.print(message, style="bold bright_white")
    elif style == "result":
        console.print(" > ", style="bold bright_green", end="")
        console.print(message, style="white")
    elif style == "info":
        console.print(message, style="bright_black")
    elif style == "error":
        console.print(message, style="red")
    else:
        console.print(message)


async def print_heading():
    async with aiofiles.open(BASE_PATH / "demetra/services/tui/header.txt") as file:
        text = await file.read()

    text = Text(text)
    text.stylize("magenta", 0, 150)
    text.stylize("cyan", 150, 250)
    text.stylize("blue", 250, 350)
    console.print(text)

    console.print("\n")
