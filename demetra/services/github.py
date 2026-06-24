import hashlib
import hmac
import json
import logging
from pathlib import Path

from demetra.library import MERGE_COMMAND_PATTERN, REBASE_COMMAND_PATTERN
from demetra.services.database import get_session_by_pr_link
from demetra.services.queue import queue
from demetra.services.subprocess import run_command
from demetra.settings import GITHUB


logger = logging.getLogger(__name__)


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """Verify GitHub webhook signature."""
    secret = GITHUB.get("webhook", {}).get("secret")
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    signature = signature_header.split("=")[1]
    expected_digest = hmac.new(key=secret.encode(), msg=payload_body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_digest)


def extract_pr_link(stdout: str) -> str | None:
    """Extract PR URL from command output."""
    for line in stdout.splitlines():
        line = line.strip()
        if "github.com" in line and "/pull/" in line:
            return line.split()[0] if line.split() else line
    return None


async def get_pr_info(pr_number: int, full_name: str, target_path: Path, env: dict) -> tuple[str, str] | None:
    """Retrieves PR head and base branch names using GitHub CLI."""
    pr_cmd = [
        str(GITHUB["path"]),
        "pr",
        "view",
        str(pr_number),
        "--json",
        "headRefName,baseRefName",
        "-R",
        full_name,
    ]
    exit_code, stdout, stderr = await run_command(command=pr_cmd, target_path=target_path, env=env)
    if exit_code != 0:
        logger.error(f"Failed to get PR info for PR #{pr_number}: {stderr.strip()}")
        return None

    try:
        pr_data = json.loads(stdout)
        return pr_data["headRefName"], pr_data["baseRefName"]
    except (ValueError, KeyError) as e:
        logger.error(f"Failed to parse PR info for PR #{pr_number}: {e}")
        return None


async def create_pull_request(
    target_path: Path,
    branch_name: str,
    title: str,
    base: str = "master",
    body: str | None = None,
    env: dict | None = None,
) -> tuple[int, str, str]:
    """Create a pull request using GitHub CLI."""
    cmd = [
        str(GITHUB["path"]),
        "pr",
        "create",
        "--title",
        title,
        "--base",
        base,
        "--head",
        branch_name,
    ]
    if body:
        cmd.extend(["--body", body])
    return await run_command(command=cmd, target_path=target_path, env=env)


async def pr_comment(pr_number: int, full_name: str, body: str, target_path: Path, env: dict) -> bool:
    """Add a comment to a GitHub PR using GitHub CLI."""
    cmd = [
        str(GITHUB["path"]),
        "pr",
        "comment",
        str(pr_number),
        "--body",
        body,
        "-R",
        full_name,
    ]
    exit_code, _, stderr = await run_command(command=cmd, target_path=target_path, env=env)
    if exit_code != 0:
        logger.error(f"Failed to comment on PR #{pr_number}: {stderr.strip()[:500]}")
        return False
    return True


async def clone_repo(repo_url: str, parent_path: Path, target_path: Path) -> dict:
    """Clone a repository."""
    if target_path.exists():
        return {"cloned": False}
    cmd = [str(GITHUB["path"]), "repo", "clone", repo_url, str(target_path)]
    exit_code, _, stderr = await run_command(command=cmd, target_path=parent_path)
    if exit_code != 0:
        raise RuntimeError(f"Failed to clone repository: {stderr}")
    return {"cloned": True}


def _is_pr_authorization(payload: dict) -> bool:
    """Check whether the comment author has write access to the repository."""
    comment = payload.get("comment", {})
    author = comment.get("user", {})
    author_association = comment.get("author_association", "").upper()

    privileged_associations = {"OWNER", "MEMBER", "COLLABORATOR", "CONTRIBUTOR"}
    if author_association in privileged_associations:
        return True

    repository = payload.get("repository", {})
    owner = repository.get("owner", {})
    if isinstance(owner, dict) and author.get("login") == owner.get("login"):
        return True

    return False


async def webhook_rebase_handler(payload: dict) -> dict:
    comment = payload.get("comment", {})
    body = comment.get("body", "")
    if not body:
        return {"action": "ignored", "reason": "no comment body"}

    issue = payload.get("issue", {})
    if not issue.get("pull_request"):
        return {"action": "ignored", "reason": "not a PR comment"}

    if not _is_pr_authorization(payload=payload):
        return {"action": "ignored", "reason": "unauthorized user"}

    repo = payload.get("repository", {})
    full_name = repo.get("full_name", "")
    pr_number = issue.get("number")
    if not full_name or not pr_number:
        return {"action": "ignored", "reason": "missing repo info or PR number"}

    pr_link = f"https://github.com/{full_name}/pull/{pr_number}"

    if MERGE_COMMAND_PATTERN.search(body):
        from demetra.workflows.merge import run_merge_workflow  # noqa: PLC0415

        session = await get_session_by_pr_link(pr_link=pr_link)
        if not session or not session.project_id:
            return {"action": "ignored", "reason": "no session found"}
        queue.enqueue(
            run_merge_workflow,
            task_id=session.task_id,
            project_id=session.project_id,
            pr_number=pr_number,
            full_name=full_name,
        )
        return {"action": "enqueued_merge", "pr_number": pr_number, "repository": full_name}

    if REBASE_COMMAND_PATTERN.search(body):
        from demetra.workflows.rebase import run_rebase_workflow  # noqa: PLC0415

        session = await get_session_by_pr_link(pr_link=pr_link)
        if not session or not session.project_id:
            return {"action": "ignored", "reason": "no session found"}
        queue.enqueue(
            run_rebase_workflow,
            task_id=session.task_id,
            project_id=session.project_id,
            pr_number=pr_number,
            full_name=full_name,
        )
        return {"action": "enqueued_rebase", "pr_number": pr_number, "repository": full_name}

    return {"action": "ignored", "reason": "no recognized command"}
