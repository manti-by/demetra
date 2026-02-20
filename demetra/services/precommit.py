from pathlib import Path

from demetra.services.subprocess import run_command


async def precommit_agent(target_path: Path, session_id: str | None = None) -> str:
    """Run pre-commit checks on the target path.

    Args:
        target_path: Path to run pre-commit checks on
        session_id: Session ID for continuity (not used in this agent)

    Returns:
        Result output from the checks

    Raises:
        RuntimeError: If pre-commit checks fail
    """
    # Run ty check first
    try:
        ty_result = await run_command(command=["ty", "check"], target_path=target_path)
    except Exception as e:
        raise RuntimeError(f"ty check failed: {e}")

    # Run pre-commit run
    try:
        precommit_result = await run_command(command=["pre-commit", "run"], target_path=target_path)
    except Exception as e:
        raise RuntimeError(f"pre-commit run failed: {e}")

    return f"ty check passed\n{ty_result}\npre-commit run passed\n{precommit_result}"
