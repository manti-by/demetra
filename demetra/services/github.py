import hashlib
import hmac
import json
import logging
from pathlib import Path

import aiohttp

from demetra.library import MERGE_COMMAND_PATTERN, REBASE_COMMAND_PATTERN
from demetra.services.database import get_session_by_pr_link
from demetra.services.queue import queue
from demetra.services.subprocess import run_command
from demetra.settings import GITHUB


logger = logging.getLogger(__name__)


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """Verify a GitHub webhook payload against its HMAC-SHA256 signature.

    Args:
        payload_body: The raw webhook request body.
        signature_header: The ``X-Hub-Signature-256`` header value.

    Returns:
        bool: True when the signature matches the configured webhook secret.
    """
    secret = GITHUB.get("webhook", {}).get("secret")
    if not secret:
        logger.warning("Webhook secret is not configured — rejecting all webhooks")
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    signature = signature_header.split("=", maxsplit=1)[1]
    expected_digest = hmac.new(key=secret.encode(), msg=payload_body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_digest)


def extract_pr_link(stdout: str) -> str | None:
    """Extract the PR URL from a command output line.

    Args:
        stdout: The command output to scan.

    Returns:
        str | None: The first GitHub pull request URL found, or None.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if "github.com" in line and "/pull/" in line:
            return line.split()[0] if line.split() else line
    return None


async def get_pr_info(pr_number: int, full_name: str, target_path: Path, env: dict) -> tuple[str, str] | None:
    """Fetch the head and base branch names of a pull request.

    Args:
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.
        target_path: Directory to run the GitHub CLI in.
        env: Environment overrides for the subprocess.

    Returns:
        tuple[str, str] | None: The head and base branch names, or None on
            failure.
    """
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
    """Create a pull request for a branch using the GitHub CLI.

    Args:
        target_path: Directory to run the GitHub CLI in.
        branch_name: The head branch of the pull request.
        title: The pull request title.
        base: The base branch, defaulting to ``"master"``.
        body: Optional pull request body.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the command.
    """
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
    """Post a comment on a GitHub pull request using the GitHub CLI.

    Args:
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.
        body: The comment body.
        target_path: Directory to run the GitHub CLI in.
        env: Environment overrides for the subprocess.

    Returns:
        bool: True when the comment was posted successfully.
    """
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
    """Clone a repository into the target path if it does not exist yet.

    Args:
        repo_url: The repository clone URL.
        parent_path: Directory to run the GitHub CLI in.
        target_path: Destination directory for the clone.

    Returns:
        dict: ``{"cloned": False}`` when the target already exists, otherwise
            ``{"cloned": True}``.

    Raises:
        RuntimeError: When the clone fails.
    """
    if target_path.exists():
        return {"cloned": False}
    cmd = [str(GITHUB["path"]), "repo", "clone", repo_url, str(target_path)]
    exit_code, _, stderr = await run_command(command=cmd, target_path=parent_path)
    if exit_code != 0:
        raise RuntimeError(f"Failed to clone repository: {stderr}")
    return {"cloned": True}


async def _is_pr_authorization(payload: dict) -> bool:
    """Check whether a comment author is authorized to trigger PR actions.

    The author is authorized when they own the repository or hold write/admin
    collaborator permission on it.

    Args:
        payload: The GitHub webhook payload.

    Returns:
        bool: True when the comment author is authorized.
    """
    comment = payload.get("comment", {})
    repository = payload.get("repository", {})

    repo_owner = repository.get("owner", {}).get("login", "")
    repo_name = repository.get("name", "")
    comment_author = comment.get("user", {}).get("login", "")

    if repo_owner and comment_author and repo_owner == comment_author:
        return True

    if not repo_owner or not repo_name or not comment_author:
        return False

    token = GITHUB.get("token")
    if not token:
        return False

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/collaborators/{comment_author}/permission"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            ) as response:
                if response.status != 200:
                    return False
                data = await response.json()
                permission = data.get("permission", "")
                return permission in ("write", "admin")
    except (aiohttp.ClientError, TimeoutError):
        return False


async def webhook_rebase_handler(payload: dict) -> dict:
    """Handle a GitHub webhook payload for merge/rebase commands on PR comments.

    Authorizes the comment author, looks up the session for the PR, and
    enqueues the matching merge or rebase workflow when the comment body
    contains the recognized command.

    Args:
        payload: The GitHub webhook payload.

    Returns:
        dict: A result describing the action taken or the reason it was
            ignored.
    """
    comment = payload.get("comment", {})
    body = comment.get("body", "")
    if not body:
        return {"action": "ignored", "reason": "no comment body"}

    issue = payload.get("issue", {})
    if not issue.get("pull_request"):
        return {"action": "ignored", "reason": "not a PR comment"}

    if not await _is_pr_authorization(payload=payload):
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
