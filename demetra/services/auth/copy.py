import asyncio
import logging
import shutil
from pathlib import Path

from demetra.services.runtime.tui import print_message


logger = logging.getLogger(__name__)


async def copy_auth_from_parent(parent_home: Path | None) -> None:
    """Copy auth configuration from a parent home directory when running in a sandbox.

    Copies the opencode, GitHub CLI and Claude Code config (``~/.claude`` minus
    session transcripts, plus the ``~/.claude.json`` account/onboarding state
    file the CLI keeps outside that directory) from the parent home into the
    current user's home when they differ, so that tooling inside the sandbox
    inherits the host's credentials.

    Args:
        parent_home: Path of the parent OS home directory, or None to skip.
    """
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

    claude_src = parent_home / ".claude"
    claude_dst = current_home / ".claude"
    if claude_src.is_dir():
        try:
            # Copy auth/config, not session transcripts or project history:
            # ~/.claude/projects holds per-project session transcripts (also
            # read by demetra/services/agents/claude.py for token usage) and
            # is potentially large and sensitive; it carries no auth material.
            await asyncio.to_thread(
                shutil.copytree,
                claude_src,
                claude_dst,
                ignore=shutil.ignore_patterns("projects"),
                dirs_exist_ok=True,
            )
            copied_anything = True
            print_message(f"Copied Claude Code config from {claude_src}", style="result")
        except Exception:
            logger.exception("Failed to copy Claude Code config from %s", claude_src)

    claude_state_src = parent_home / ".claude.json"
    claude_state_dst = current_home / ".claude.json"
    if claude_state_src.is_file():
        try:
            await asyncio.to_thread(shutil.copy2, claude_state_src, claude_state_dst)
            copied_anything = True
            print_message(f"Copied Claude Code state from {claude_state_src}", style="result")
        except Exception:
            logger.exception("Failed to copy Claude Code state from %s", claude_state_src)

    if not copied_anything:
        print_message("No auth files found in parent OS home", style="info")
