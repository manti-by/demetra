from pathlib import Path

from demetra.services.opencode import opencode_build_agent


async def run_build_agent(
    target_path: Path, task: str, session_id: str | None = None, task_title: str | None = None
) -> tuple[int, str, str]:
    return await opencode_build_agent(target_path=target_path, task=task, session_id=session_id, task_title=task_title)
