import asyncio
import logging
import shutil
from pathlib import Path

from demetra.services.tui import print_message


logger = logging.getLogger(__name__)


async def copy_auth_from_parent(parent_home: Path | None) -> None:
    if not parent_home or not parent_home.is_dir():
        return

    current_home = Path.home()
    if parent_home.resolve() == current_home.resolve():
        print_message(
            "Parent home is the same as current home, skipping auth copy",
            style="info",
        )
        return

    copied_anything = False

    opencode_src = parent_home / ".config" / "opencode"
    opencode_dst = current_home / ".config" / "opencode"
    if opencode_src.is_dir():
        try:
            await asyncio.to_thread(shutil.copytree, opencode_src, opencode_dst, dirs_exist_ok=True)
            copied_anything = True
            print_message(f"Copied opencode config from {opencode_src}", style="result")
        except Exception:
            logger.exception("Failed to copy opencode config from %s", opencode_src)

    gh_src = parent_home / ".config" / "gh"
    gh_dst = current_home / ".config" / "gh"
    if gh_src.is_dir():
        try:
            await asyncio.to_thread(shutil.copytree, gh_src, gh_dst, dirs_exist_ok=True)
            copied_anything = True
            print_message(f"Copied gh auth from {gh_src}", style="result")
        except Exception:
            logger.exception("Failed to copy gh auth from %s", gh_src)

    if not copied_anything:
        print_message("No auth files found in parent OS home", style="info")
