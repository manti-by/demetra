import hashlib
import hmac
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from demetra.library import MERGE_COMMAND_PATTERN, REBASE_COMMAND_PATTERN
from demetra.services.persistence.database import get_session_by_pr_link
from demetra.services.persistence.queue import queue
from demetra.services.runtime.subprocess import run_command
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


GITHUB_HOSTS = {"github.com", "www.github.com"}


def extract_pr_link(stdout: str) -> str | None:
    """Extract the PR URL from a command output line.

    Args:
        stdout: The command output to scan.

    Returns:
        str | None: The first GitHub pull request URL found, or None.
    """
    for line in stdout.splitlines():
        candidate = line.strip().split(maxsplit=1)[0] if line.strip() else ""
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in GITHUB_HOSTS:
            continue
        if "pull" in parsed.path.split("/"):
            return candidate
    return None


async def get_pr_info(
    pr_number: int,
    full_name: str,
    target_path: Path,
    env: dict,
    project_id: str | None = None,
) -> tuple[str, str] | None:
    """Fetch the head and base branch names of a pull request.

    Args:
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.
        target_path: Directory to run the GitHub CLI in.
        env: Environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

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
    exit_code, stdout, stderr = await run_command(
        command=pr_cmd, target_path=target_path, env=env, project_id=project_id
    )
    if exit_code != 0:
        logger.error(f"Failed to get PR info for PR #{pr_number}: {stderr.strip()}")
        return None

    try:
        pr_data = json.loads(stdout)
        return pr_data["headRefName"], pr_data["baseRefName"]
    except (ValueError, KeyError) as e:
        logger.error(f"Failed to parse PR info for PR #{pr_number}: {e}")
        return None


async def get_unresolved_review_threads(
    pr_number: int,
    full_name: str,
    target_path: Path,
    env: dict,
    project_id: str | None = None,
) -> list[dict]:
    """Fetch unresolved review threads for a pull request via the GitHub CLI.

    Uses ``gh api graphql`` to query ``reviewThreads``. The GraphQL connection
    has no ``isResolved`` filter, so resolved threads are discarded here after
    the query returns. Returns threads from any author, both inline and
    general review comments. General review bodies come from ``latestReviews``,
    which holds each reviewer's most recent submission, so a reviewer who has
    since approved or dismissed their request no longer surfaces as
    actionable.

    Args:
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.
        target_path: Directory to run the GitHub CLI in.
        env: Environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        list[dict]: Unresolved review threads, each with its comment nodes.
    """
    try:
        owner, repo = full_name.split("/", 1)
    except ValueError as e:
        raise RuntimeError(f"Invalid full_name for review threads: {full_name!r}") from e

    query = (
        "query($owner:String!,$name:String!,$pr:Int!){"
        "repository(owner:$owner,name:$name){"
        "pullRequest(number:$pr){"
        "reviewThreads(first:100){pageInfo{hasNextPage} nodes{isResolved isOutdated path line comments(first:100){pageInfo{hasNextPage} nodes{body path diffHunk line originalLine author{login} createdAt}}}"
        "} latestReviews(first:100){pageInfo{hasNextPage} nodes{body author{login} createdAt state}}"
        "}}}"
    )

    command = [
        str(GITHUB["path"]),
        "api",
        "graphql",
        "-f",
        f"query={query}",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={repo}",
        "-F",
        f"pr={pr_number}",
    ]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, env=env, project_id=project_id, disable_stdio=True
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to fetch review threads for PR #{pr_number}: {stderr.strip()[:500]}")

    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"Failed to parse review threads for PR #{pr_number}: {e}") from e

    try:
        pr_data = data["data"]["repository"]["pullRequest"]
        rt = pr_data["reviewThreads"]
        nodes = rt["nodes"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Unexpected review threads payload for PR #{pr_number}: {e}") from e

    if rt.get("pageInfo", {}).get("hasNextPage"):
        raise RuntimeError(f"Review threads truncated at 100 for PR #{pr_number}; pagination required")
    for thread in nodes:
        comments = thread.get("comments", {})
        if isinstance(comments, dict) and comments.get("pageInfo", {}).get("hasNextPage"):
            raise RuntimeError(f"Comments truncated at 100 for a thread on PR #{pr_number}; pagination required")

    latest_reviews_data = pr_data.get("latestReviews", {})
    if isinstance(latest_reviews_data, dict) and latest_reviews_data.get("pageInfo", {}).get("hasNextPage"):
        raise RuntimeError(f"Latest reviews truncated at 100 for PR #{pr_number}; pagination required")

    unresolved: list[dict] = []
    for thread in nodes:
        if not isinstance(thread, dict):
            continue
        if thread.get("isResolved"):
            continue
        unresolved.append(thread)

    # General (non-inline) review bodies are not in reviewThreads; surface them as pseudo-threads
    # so Request-Changes summaries without inline comments are not silently ignored.
    # latestReviews already collapses submissions to each reviewer's current state,
    # so the CHANGES_REQUESTED filter only matches currently actionable feedback.
    try:
        reviews = latest_reviews_data.get("nodes", []) if isinstance(latest_reviews_data, dict) else []
        for review in reviews:
            if not isinstance(review, dict):
                continue
            if review.get("state") != "CHANGES_REQUESTED":
                continue
            body = (review.get("body") or "").strip()
            if not body:
                continue
            unresolved.append(
                {
                    "isResolved": False,
                    "path": "",
                    "line": None,
                    "isOutdated": False,
                    "comments": {"nodes": [review]},
                }
            )
    except (KeyError, TypeError):
        logger.warning(f"Failed to process general reviews for PR #{pr_number}", exc_info=True)

    return unresolved


async def create_pull_request(
    target_path: Path,
    branch_name: str,
    title: str,
    base: str = "master",
    body: str | None = None,
    env: dict | None = None,
    project_id: str | None = None,
) -> tuple[int, str, str]:
    """Create a pull request for a branch using the GitHub CLI.

    Args:
        target_path: Directory to run the GitHub CLI in.
        branch_name: The head branch of the pull request.
        title: The pull request title.
        base: The base branch, defaulting to ``"master"``.
        body: Optional pull request body.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

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
    return await run_command(command=cmd, target_path=target_path, env=env, project_id=project_id)


async def pr_comment(
    pr_number: int,
    full_name: str,
    body: str,
    target_path: Path,
    env: dict,
    project_id: str | None = None,
) -> bool:
    """Post a comment on a GitHub pull request using the GitHub CLI.

    Args:
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.
        body: The comment body.
        target_path: Directory to run the GitHub CLI in.
        env: Environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

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
    exit_code, _, stderr = await run_command(command=cmd, target_path=target_path, env=env, project_id=project_id)
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
