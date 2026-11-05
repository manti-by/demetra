# 04 — Root `chown` follows symlinks in an app-writable home

## Summary

- **Title:** Privileged ownership repair dereferences application-controlled paths
- **Problem:** The container entrypoint runs as root and `chown`s paths inside
  `/home/demetra` (an application-writable home) without rejecting symlinks. A
  repository-controlled test running as `demetra` can plant a symlink at
  `.config/gh` or `.local/share/opencode`; a later root startup follows it and grants
  the application account authority to replace privileged configuration.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-59** · **Category:** path_traversal
- **CodeRabbit ID:** `b4f14e31-a89c-4c16-97db-9dd2326af5b7`
- **Files (current):** `configs/docker-entrypoint.sh:8-19`
- **Revalidation:** Confirmed. The `find ... -exec chown -h` uses `-h` (no-dereference),
  but the direct `chown demetra:demetra /home/demetra/.config/gh
  /home/demetra/.local/share/opencode` at line 19 (and the `mkdir -p` at line 18)
  still follow symlinks.

## Steps

1. Use `chown -h` (`--no-dereference`) on every ownership-repair path, including the
   direct `chown` at `configs/docker-entrypoint.sh:19`.
2. Before `mkdir -p` / `chown` of `.config/gh` and `.local/share/opencode`, reject or
   remove any symlink at those exact paths (e.g. `test -L ... && rm ...`), so the
   repaired directory is the intended directory.
3. Prefer repairing ownership on the bind-mount *sources* at image build time
   (`docker-compose.yaml` already mounts `.keys/gh/hosts.yml` and
   `.keys/opencode/auth.json` individually) rather than inside the app-writable home.
4. Retain directory handles and change ownership through those handles where possible,
   and drop privileges earlier so root never repairs app-writable paths.
