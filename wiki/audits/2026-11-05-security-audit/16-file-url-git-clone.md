# 16 — `file://` URL accepted for service-managed clone

## Summary

- **Title:** GitHub URL validator accepts `file://` and clones from local paths
- **Problem:** `parse_github_url` falls back to `urlparse` and accepts any URL whose
  hostname is `github.com`/`www.github.com` — including `file://github.com/owner/repo`,
  whose scheme is never checked. Provisioning then passes the caller's *original* URL to
  `git clone`, so Git interprets the path as a local repository, letting a project
  creator copy private repository contents/history outside the intended GitHub boundary.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-200** · **Category:** sensitive_data_exposure
- **CodeRabbit ID:** `280de93e-d07e-4e42-b319-41a2068d7f41`
- **Files (current):** `demetra/services/runtime/project.py:68-109`
  (`parse_github_url`), `demetra/services/runtime/project.py:140-145`
  (`setup_project_directory`)
- **Revalidation:** Confirmed. `parse_github_url` checks only `parsed.hostname in
  GITHUB_HOSTS` (lines 98-99) without inspecting `parsed.scheme`, and
  `setup_project_directory` clones `project["repository_url"]` (the original value).
  (Scanner assumption A3: shared-volume deployment lets the API and workers share the
  checkout storage.)

## Steps

1. In `parse_github_url`, reject non-GitHub schemes: only accept the explicit HTTPS/SSH
   patterns, and for the urlparse fallback require `parsed.scheme in ("", "https",
   "http")` (or `None`) before matching the hostname — explicitly reject `file`,
   `git`, `ftp`, etc.
2. Reconstruct the clone URL from validated `owner`/`repo` components
   (`https://github.com/{owner}/{repo}.git`) instead of passing the caller's original
   URL to `git clone`.
3. Harden service-managed cloning against local transports, e.g.
   `git -c protocol.file.allow=never clone ...`, so even a mis-validated URL cannot read
   local repositories.
4. Add tests: `file://github.com/owner/repo` is rejected; `https`/`ssh` forms still
   parse to `(owner, repo)`.
