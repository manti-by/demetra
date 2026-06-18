import hmac
import json
import logging
import re
import tempfile
from pathlib import Path

from demetra.services.git import git_checkout, git_fetch, git_force_push, git_rebase
from demetra.services.subprocess import run_command
from demetra.settings import GITHUB


logger = logging.getLogger(__name__)

_PR_LINK_RE = re.compile(r"https?://[^/\s]+/[^/\s]+/[^/\s]+/pull/\d+")


def extract_pr_link(stdout: str) -> str | None:
    match = _PR_LINK_RE.search(stdout)
    return match.group(0) if match else None


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    if not (secret := GITHUB["webhook"].get("secret")):
        return True

    if not signature_header:
        return False

    expected_prefix = "sha256="
    if not signature_header.startswith(expected_prefix):
        return False

    signature = signature_header[len(expected_prefix) :]
    digest = hmac.new(key=secret.encode(), msg=payload_body, digestmod="sha256").hexdigest()

    return hmac.compare_digest(digest, signature)


async def create_pull_request(
    target_path: Path, branch_name: str, title: str, base: str = "master", env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    command = [
        str(GITHUB["path"]),
        "pr",
        "create",
        "--base",
        base,
        "--head",
        branch_name,
        "--title",
        title,
        "--body",
        "",
    ]
    return await run_command(command=command, target_path=target_path, env=env)


async def get_pr_info(repo_path: Path, pr_number: int) -> dict:
    command = [
        str(GITHUB["path"]),
        "pr",
        "view",
        str(pr_number),
        "--json",
        "headRefName,baseRefName,headRepository,state,body",
    ]
    exit_code, stdout, stderr = await run_command(command=command, target_path=repo_path)
    if exit_code != 0:
        raise RuntimeError(f"Failed to get PR info: {stderr.strip()}")

    return json.loads(stdout)


async def clone_repo(repo_url: str, parent_path: Path, target_path: Path) -> dict:
    logger.info("Cloning repository %s to %s", repo_url, target_path)

    command = [str(GITHUB["path"]), "repo", "clone", repo_url, str(target_path), "--"]
    exit_code, _, stderr = await run_command(command=command, target_path=parent_path)
    if exit_code != 0:
        raise RuntimeError(f"Failed to clone repository: {stderr.strip()}")

    return {"cloned": True}


async def rebase_pr_branch(repo_url: str, pr_number: int) -> bool:
    with tempfile.TemporaryDirectory(prefix="demetra-rebase-") as tmpdir:
        tmp_path = Path(tmpdir)
        clone_path = tmp_path / "repo"

        await clone_repo(repo_url=repo_url, parent_path=tmp_path, target_path=clone_path)

        pr_info = await get_pr_info(repo_path=clone_path, pr_number=pr_number)
        head_branch = pr_info["headRefName"]
        base_branch = pr_info["baseRefName"]

        logger.info("Rebasing PR #%s: %s onto %s", pr_number, head_branch, base_branch)

        await git_fetch(target_path=clone_path)
        await git_checkout(target_path=clone_path, branch_name=head_branch)
        await git_rebase(target_path=clone_path, base_branch=base_branch)
        await git_force_push(target_path=clone_path, branch_name=head_branch)

        logger.info("Successfully rebased and pushed PR #%s (%s)", pr_number, head_branch)

        return True


async def webhook_rebase_handler(payload: dict) -> dict:
    comment_body = payload.get("comment", {}).get("body", "")
    if "rebase" not in comment_body.lower():
        return {"action": "ignored", "reason": "no rebase keyword"}

    issue = payload.get("issue", {})
    if not issue.get("pull_request"):
        return {"action": "ignored", "reason": "not a PR comment"}

    pr_number = issue.get("number")

    repository = payload.get("repository", {})
    clone_url = repository.get("clone_url") or repository.get("html_url")
    full_name = repository.get("full_name", "")

    if not clone_url or not pr_number:
        return {"action": "ignored", "reason": "missing repo URL or PR number"}

    logger.info("Rebase triggered by comment on PR #%s in %s", pr_number, full_name)

    await rebase_pr_branch(repo_url=clone_url, pr_number=pr_number)

    return {"action": "rebased", "pr_number": pr_number, "repository": full_name}
