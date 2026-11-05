# 05 — `GIT_SSH_COMMAND` project environment injection

## Summary

- **Title:** Project environment can replace the Git transport interpreter
- **Problem:** Service-managed Git operations (`git pull`, `git push`, `git fetch`,
  `git clone`) forward arbitrary project environment values, including
  `GIT_SSH_COMMAND`. For an SSH remote, Git executes that value as a shell command
  with the worker's identity, giving an ordinary project owner access beyond their
  project.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-78** · **Category:** injection
- **CodeRabbit ID:** `a9069a4a-25e8-4f54-9532-d1c22e1f0cb7`
- **Files (current):** `demetra/services/runtime/subprocess.py:32-69,93-138`
  (`build_subprocess_env`, `run_command`), `demetra/services/vcs/git.py:301-316`
  (`git_pull`)
- **Revalidation:** Confirmed. `build_subprocess_env` merges `environment.subprocess_env`
  (project values) unfiltered, and `git_pull`/`git_push`/`git_fetch`/`setup_project_directory`
  pass the resolved environment into `run_command`.

## Steps

1. Construct a controlled environment for service-managed Git: in a Git-specific
   wrapper (or a `run_command` flag), drop tenant-controlled keys that Git interprets
   as executable configuration — at minimum `GIT_SSH_COMMAND`, `GIT_SSH`,
   `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_*`,
   `GIT_EXEC_PATH`, and `GIT_PROXY_COMMAND`.
2. Pass only the OS-allowlisted `SSH_*` values (e.g. `SSH_AUTH_SOCK`) that the worker
   itself provides, not project-supplied overrides.
3. Run project execution under a separate identity with project-scoped files and
   credentials (see plan 18), so a successful transport override cannot reach shared
   service credentials.
4. Add a test that a project env entry `GIT_SSH_COMMAND=...` is not present in the
   environment passed to `git pull`/`git push`.
