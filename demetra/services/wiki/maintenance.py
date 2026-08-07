import re
from pathlib import Path

import demetra.services.wiki as service


def page_tokens(meta: dict, body: str) -> set[str]:
    """Split a page's metadata and body into a token set for dedup scoring.

    Args:
        meta: The page frontmatter mapping.
        body: The page body text.

    Returns:
        set[str]: The lowercase token set of title, tags, tickets and body.
    """
    text = " ".join(
        [
            str(meta.get("title") or ""),
            " ".join(str(item) for item in (meta.get("tags") or [])),
            " ".join(str(item) for item in (meta.get("tickets") or [])),
            body,
        ]
    )
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if len(token) > 2}


def similarity(left: set[str], right: set[str]) -> float:
    """Compute the Jaccard similarity of two token sets.

    Args:
        left: The first token set.
        right: The second token set.

    Returns:
        float: The Jaccard similarity in ``[0, 1]``.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


async def answer_sweep() -> int:
    """Apply answered ``## Open`` entries in QUESTIONS.md and move them to Resolved.

    Returns:
        int: The number of questions resolved.
    """
    if not service.QUESTIONS_PATH.is_file():
        return 0
    text = service.QUESTIONS_PATH.read_text(encoding="utf-8")
    if "## Open" not in text:
        return 0

    header, _, rest = text.partition("## Open")
    open_block, _, resolved_block = rest.partition("## Resolved")

    kept: list[str] = []
    resolved: list[str] = []
    current: list[str] = []
    count = 0
    for line in open_block.splitlines():
        if line.strip().startswith("### "):
            if current:
                entry_text = "\n".join(current)
                if service.has_answer(entry_text):
                    count += 1
                    resolved.append(entry_text)
                else:
                    kept.append(entry_text)
            current = [line]
        else:
            current.append(line)
    if current:
        entry_text = "\n".join(current)
        if service.has_answer(entry_text):
            count += 1
            resolved.append(entry_text)
        else:
            kept.append(entry_text)

    if not count:
        return 0

    open_section = "\n\n".join(kept)
    resolved_section = (
        "\n\n".join([*resolved, resolved_block.strip()]) if resolved_block.strip() else "\n\n".join(resolved)
    )
    new_text = (
        f"{header}## Open\n\n{open_section}\n\n## Resolved\n\n{resolved_section}\n"
        if open_section.strip()
        else f"{header}## Open\n\n_Newest first._\n\n## Resolved\n\n{resolved_section}\n"
    )
    service.QUESTIONS_PATH.write_text(encoding="utf-8", data=new_text)
    return count


def has_answer(entry_text: str) -> bool:
    """Check whether a question entry has a filled-in answer.

    A question counts as answered only when the ``**Answer:**`` field holds
    non-whitespace content beyond the template placeholder.

    Args:
        entry_text: The raw question entry text.

    Returns:
        bool: True when the ``**Answer:**`` field holds real content.
    """
    if "**Answer:**" not in entry_text:
        return False
    _, _, value = entry_text.partition("**Answer:**")
    answer = value.strip().lstrip("*").strip()
    if not answer:
        return False
    if re.search(r"^(?:\(?_|_?\(|left blank)", answer):
        return False
    return True


async def dedup_pages() -> tuple[int, int]:
    """Merge near-duplicate wiki pages keeping the most recent version.

    Returns:
        tuple[int, int]: The number of pages merged and deleted.
    """
    if not service.PAGES_ROOT.is_dir():
        return 0, 0
    parsed: dict[Path, dict] = {}
    for path in sorted(service.PAGES_ROOT.glob("*.md")):
        page = service.parse_page_file(path=path)
        if page is not None:
            parsed[path] = page

    merged = 0
    deleted: list[Path] = []
    candidates = list(parsed)
    for index, left_path in enumerate(candidates):
        if left_path in deleted:
            continue
        for right_path in candidates[index + 1 :]:
            if right_path in deleted:
                continue
            left, right = parsed[left_path], parsed[right_path]
            tokens_left = service.page_tokens(meta=left["meta"], body=left["body"])
            tokens_right = service.page_tokens(meta=right["meta"], body=right["body"])
            if service.similarity(tokens_left, tokens_right) < service.DEDUP_SIMILARITY_THRESHOLD:
                continue
            survivor = service.pick_survivor(left_path=left_path, right_path=right_path)
            if survivor is None:
                continue
            survivor_path, loser_path = survivor
            if service.merge_page_content(survivor_path=survivor_path, loser_path=loser_path, parsed=parsed):
                merged += 1
                deleted.append(loser_path)
                refreshed = service.parse_page_file(path=survivor_path)
                if refreshed is not None:
                    parsed[survivor_path] = refreshed

    for path in deleted:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            service.logger.warning(f"Failed to delete duplicate wiki page {path.name}")
    if deleted:
        await service.prune_index_pages(deleted_names=[path.name for path in deleted])
    return merged, len(deleted)


def pick_survivor(left_path: Path, right_path: Path) -> tuple[Path, Path] | None:
    """Pick the survivor of a near-duplicate pair by frontmatter date.

    Args:
        left_path: The first page path.
        right_path: The second page path.

    Returns:
        tuple[Path, Path] | None: The ``(survivor, loser)`` paths, or None when
            both dates are equal.
    """
    left_date = service.page_date(left_path)
    right_date = service.page_date(right_path)
    if left_date == right_date:
        return None
    if left_date > right_date:
        return left_path, right_path
    return right_path, left_path


def merge_page_content(survivor_path: Path, loser_path: Path, parsed: dict) -> bool:
    """Merge a duplicate page's frontmatter lists and body into the survivor.

    Args:
        survivor_path: The surviving page path.
        loser_path: The page to merge in.
        parsed: The parsed pages mapping used to read frontmatter.

    Returns:
        bool: True when the survivor was written successfully, False when the
            write failed and the loser must not be deleted.
    """
    survivor = parsed[survivor_path]
    loser = parsed[loser_path]
    survivor_meta = dict(survivor["meta"])
    loser_meta = loser["meta"]
    for key in ("tags", "related", "tickets", "services"):
        union = list(dict.fromkeys([*(survivor_meta.get(key) or []), *(loser_meta.get(key) or [])]))
        if loser_path.name in union:
            union.remove(loser_path.name)
        survivor_meta[key] = union

    survivor_body = survivor["body"]
    loser_body = loser["body"]
    merged_body = survivor_body
    for section in re.split(r"(?=^#{1,3} )", loser_body, flags=re.MULTILINE):
        if section.strip() and section.strip() not in survivor_body:
            merged_body = f"{merged_body.rstrip()}\n\n{section.strip()}"
    survivor_meta["related"] = [item for item in (survivor_meta.get("related") or []) if item != loser_path.name]

    body = service.dump_frontmatter(survivor_meta) + "\n" + merged_body.lstrip()
    try:
        survivor_path.write_text(encoding="utf-8", data=body)
    except OSError:
        service.logger.warning(f"Failed to write merged wiki page {survivor_path.name}")
        return False
    return True


async def check_agents_drift() -> list[str]:
    """Check AGENTS.md for the anchors the 2026-08-03 revalidation maintains.

    Returns:
        list[str]: The names of the drifted (missing) anchors.
    """
    if not service.AGENTS_PATH.is_file():
        return ["AGENTS.md missing"]
    text = service.AGENTS_PATH.read_text(encoding="utf-8")
    return [anchor for anchor in service.AGENTS_DRIFT_ANCHORS if anchor not in text]


async def revalidate_wiki_and_agents() -> dict:
    """Run the post-merge wiki/AGENTS.md revalidation sweep.

    Applies answered questions, merges near-duplicate pages, rebuilds the
    ``## By topic`` clusters and checks AGENTS.md drift anchors. Failures are
    logged and never raised.

    Returns:
        dict: Revision statistics keyed by pages merged, pages deleted,
            questions resolved, clusters rebuilt and drifted anchors.
    """
    stats = {
        "pages_merged": 0,
        "pages_deleted": 0,
        "questions_resolved": 0,
        "clusters_rebuilt": 0,
        "agents_drift": [],
    }
    try:
        stats["questions_resolved"] = await service.answer_sweep()
        merged, deleted = await service.dedup_pages()
        stats["pages_merged"] = merged
        stats["pages_deleted"] = deleted
        stats["clusters_rebuilt"] = await service.regenerate_by_topic()
        stats["agents_drift"] = await service.check_agents_drift()
    except Exception:  # noqa: BLE001
        service.logger.exception("Wiki revalidation failed")
    return stats


async def on_default_branch(target_path: Path) -> bool:
    """Check whether a worktree is on the repository's default branch.

    Args:
        target_path: The repository worktree.

    Returns:
        bool: True when HEAD is on the default branch.
    """
    default_ref = await service.git_default_branch(target_path=target_path, env=None)
    default_name = default_ref.removeprefix("origin/")
    command = [str(service.GIT["path"]), "rev-parse", "--abbrev-ref", "HEAD"]
    try:
        exit_code, stdout, _ = await service.run_command(command=command, target_path=target_path, disable_stdio=True)
    except (OSError, RuntimeError):
        return False
    if exit_code != 0:
        return False
    return stdout.strip() == default_name


async def commit_revalidation(stats: dict) -> str | None:
    """Commit the revalidation changes to ``wiki/`` and ``AGENTS.md``.

    Only runs on the repository's default branch. When another process holds
    the git index lock, ``REVALIDATION_RETRYABLE`` is returned so the caller can
    classify the failure as transient rather than permanent.

    Args:
        stats: The revision statistics from ``revalidate_wiki_and_agents``.

    Returns:
        str | None: The commit SHA, ``REVALIDATION_RETRYABLE`` on index lock
            contention, or None when there was nothing to commit.
    """
    if not any(
        (
            stats.get("pages_merged"),
            stats.get("pages_deleted"),
            stats.get("questions_resolved"),
            stats.get("clusters_rebuilt"),
        )
    ):
        return None

    if not await service.on_default_branch(target_path=service.BASE_PATH):
        service.logger.warning(msg="Skipping wiki revalidation commit: BASE_PATH is not on the default branch")
        return None

    command = [str(service.GIT["path"]), "add", "wiki/", "AGENTS.md"]
    exit_code, _, stderr = await service.run_command(command=command, target_path=service.BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        if "index.lock" in stderr:
            return service.REVALIDATION_RETRYABLE
        service.logger.warning(msg=f"Failed to stage revalidation changes: {stderr.strip()}")
        return None

    diff_cmd = [str(service.GIT["path"]), "diff", "--staged", "--name-only"]
    exit_code, staged, _ = await service.run_command(
        command=diff_cmd, target_path=service.BASE_PATH, disable_stdio=True
    )
    if exit_code != 0 or not staged.strip():
        return None

    message = "Revalidate wiki and AGENTS.md (post-merge)"
    commit_cmd = [str(service.GIT["path"]), "commit", "-m", message, "--", "wiki/", "AGENTS.md"]
    exit_code, _, stderr = await service.run_command(
        command=commit_cmd, target_path=service.BASE_PATH, disable_stdio=True
    )
    if exit_code != 0:
        if "index.lock" in stderr:
            return service.REVALIDATION_RETRYABLE
        service.logger.warning(msg=f"Failed to commit revalidation changes: {stderr.strip()}")
        return None

    rev_cmd = [str(service.GIT["path"]), "rev-parse", "HEAD"]
    exit_code, sha, _ = await service.run_command(command=rev_cmd, target_path=service.BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        return None
    return sha.strip() or None


async def run_wiki_revalidation() -> dict:
    """RQ job entry point: revalidate the wiki and AGENTS.md after a merge.

    Errors are logged and never raised so a revalidation failure does not fail
    the job queue.

    Returns:
        dict: The revision statistics, including the commit SHA when committed.
    """
    stats = await service.revalidate_wiki_and_agents()
    try:
        commit_result = await service.commit_revalidation(stats=stats)
        if commit_result == service.REVALIDATION_RETRYABLE:
            stats["retryable"] = True
            service.logger.warning(msg="Wiki revalidation commit blocked by git index.lock; retry later")
            commit_result = None
        stats["commit_sha"] = commit_result
    except Exception:  # noqa: BLE001
        service.logger.exception("Failed to commit wiki revalidation")
        stats["commit_sha"] = None
    service.logger.info("Wiki revalidation done: %s", stats)
    return stats
