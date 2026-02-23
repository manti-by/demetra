from pathlib import Path

from demetra.services.coderabbit import coderabbit_review_agent
from demetra.services.cursor import cursor_review_agent
from demetra.services.opencode import opencode_review_agent
from demetra.services.tui import print_message


async def run_review_agents(target_path: Path, session_id: str | None = None) -> str | None:
    print_message("Running OPENCODE REVIEW agent", style="heading")
    _, opencode_comments, _ = await opencode_review_agent(target_path=target_path, session_id=session_id)
    opencode_comments = opencode_comments.replace("No issues found.", "").strip()
    if opencode_comments:
        print_message("OpenCode review agent returned comments", style="result")
        print_message(opencode_comments, style="result")
        return opencode_comments

    print_message("Running CURSOR REVIEW agent", style="heading")
    _, cursor_comments, _ = await cursor_review_agent(target_path=target_path, session_id=session_id)
    if cursor_comments:
        print_message("Cursor review agent returned comments", style="result")
        print_message(cursor_comments, style="result")
        return cursor_comments

    # print_message("Running CODERABBIT REVIEW agent", style="heading")
    # _, coderabbit_comments, _ = await coderabbit_review_agent(target_path=target_path)
    # if coderabbit_comments:
    #     print_message("CodeRabbit review agent returned comments", style="result")
    #     print_message(coderabbit_comments, style="result")
    #     return coderabbit_comments

    print_message("No comments from any review agent, continuing the workflow.", style="result")
    return None
