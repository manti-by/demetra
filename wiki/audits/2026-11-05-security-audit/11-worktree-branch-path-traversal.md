# 11 — Branch-name worktree path deletion outside the worktree

## Summary

- **Title:** Recursive worktree cleanup can be redirected through a symlink
- **Problem:** `get_worktree_path` builds the worktree directory from
  `owner/repo/branch_name`, and `git_worktree_create` calls `shutil.rmtree` on that
  path before creating the branch or checking conflicts. A repository-controlled
  symlink in an intermediate component can redirect the recursive delete outside the
  intended worktree. Valid git ref syntax does not prevent filesystem redirection
  through tracked symlinks.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-59** · **Category:** path_traversal
- **CodeRabbit ID:** `62cac97c-468b-44c9-a104-b0dd25881c50`
- **Files (current):** `demetra/services/vcs/git.py:33-43` (`get_worktree_path`),
  `demetra/services/vcs/git.py:176-188` (`git_worktree_create`)
- **Revalidation:** Confirmed. `get_worktree_path` concatenates the branch name and
  `git_worktree_create` calls `shutil.rmtree(worktree_path)` with no symlink-ancestor
  verification. (Scanner assumption A3: shared worktree storage in the shipped Compose
  deployment.)

## Steps

1. Use flat, collision-free worktree directory names derived from `project.id` +
   `slugify(branch_name)` (or a hash) instead of raw branch path components, so `/` in
   a branch name cannot create nested directories.
2. Restrict `validate_ref` for worktree branches to a single segment (reject `/`), or
   map `/` to a safe separator in the directory component.
3. Before `shutil.rmtree`, verify the resolved path is under the worktree root and that
   no ancestor is a symlink (walk components with `lstat`, or use
   `os.path.realpath` comparison against `GIT["worktree_path"].resolve()`).
4. Perform cleanup through a trusted directory handle (e.g. `os.open` with
   `O_NOFOLLOW` / `dir_fd`) that rejects symlink ancestors before any deletion.
5. Add tests: a worktree path whose intermediate component is a symlink is refused
   rather than deleted.
