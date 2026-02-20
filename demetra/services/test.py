from pathlib import Path

from demetra.services.subprocess import run_command


async def test_agent(target_path: Path, session_id: str | None = None) -> str:
    """Run tests on the target path.

    Args:
        target_path: Path to run tests on
        session_id: Session ID for continuity (not used in this agent)

    Returns:
        Result output from the tests

    Raises:
        RuntimeError: If tests fail
    """
    try:
        result = await run_command(command=["uv", "run", "pytest", "tests/"], target_path=target_path)
        return result
    except Exception as e:
        raise RuntimeError(f"Tests failed: {e}")
