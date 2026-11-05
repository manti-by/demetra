# 06 — Listener dispatches merge/rebase without author permission

## Summary

- **Title:** Any commenter can trigger repository-changing merge/rebase work
- **Problem:** The notification listener fetches only the comment *body* and dispatches
  merge/rebase/`fix review findings` commands without checking the comment author's
  repository permissions. A user who can comment but not write can trigger work that
  force-pushes a tracked PR head using project credentials.
- **Date:** 2026-11-05
- **Severity:** low · **CWE-862** · **Category:** authorization_bypass
- **CodeRabbit ID:** `a0fd9942-2f46-40f2-a783-9608ba2b13da`
- **Files (current):** `demetra/services/daemons/listener.py:98-125`
  (`fetch_subject_body`), `demetra/services/daemons/listener.py:192-248`
  (`process_notification`)
- **Revalidation:** Confirmed. `fetch_subject_body` requests only `.body`, and
  `process_notification` enqueues without any author/permission lookup.

## Steps

1. Extend `fetch_subject_body` to also fetch the comment author
   (e.g. `--jq` returning `{body, user.login}`), and thread the author through
   `extract_pr_info` / `process_notification`.
2. In `process_notification` (or a new `_author_can_write` helper), query GitHub for
   the author's permission on the repository
   (e.g. `gh api repos/{owner}/{repo}/collaborators/{login}/permission`) and require
   `write` or `admin` before enqueuing.
3. Share this authorisation check with the webhook path
   (`demetra/services/vcs/github.py` `webhook_rebase_handler`) to avoid divergence.
4. Reject the command (log + skip) when author identity cannot be established.
5. Add tests covering a comment-only author (no write permission) and an unknown
   author.
