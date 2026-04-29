from pathlib import Path

from demetra.services.cursor import cursor_review_agent
from demetra.services.opencode import opencode_review_agent
from demetra.services.tui import print_message
from demetra.settings import OPENCODE


NO_ISSUE_TOKENS = [
    "silent",
    "no issues found.",
    "no clear, high-severity issues found.",
    "no output - no critical or error-level issues found.",
]


async def run_review_agents(target_path: Path, session_id: str | None = None) -> str | None:
    print_message("Running OPENCODE REVIEW agents", style="heading")
    for model in OPENCODE["review_models"]:
        _, opencode_comments, _ = await opencode_review_agent(
            target_path=target_path, session_id=session_id, model=model
        )
        opencode_comments = opencode_comments.strip()
        if any(phrase in opencode_comments.lower() for phrase in NO_ISSUE_TOKENS):
            opencode_comments = ""
        if opencode_comments:
            print_message(f"OpenCode review agent ({model}) returned comments", style="result")
            print_message(opencode_comments, style="result")
            return opencode_comments

    print_message("Running CURSOR REVIEW agent", style="heading")
    _, cursor_comments, _ = await cursor_review_agent(target_path=target_path, session_id=session_id)
    if cursor_comments:
        print_message("Cursor review agent returned comments", style="result")
        print_message(cursor_comments, style="result")
        return cursor_comments

    print_message("No comments from any review agent, continuing the workflow.", style="result")
    return None
