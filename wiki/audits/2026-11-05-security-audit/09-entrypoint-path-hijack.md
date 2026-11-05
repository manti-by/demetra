# 09 — Entrypoint resolves `id`/`setpriv` through an untrusted PATH

## Summary

- **Title:** Root startup executes `id` before establishing a trusted PATH
- **Problem:** `configs/docker-entrypoint.sh` executes `id -u` (and later `setpriv`)
  via `$PATH` before establishing whether it runs as root. Earlier PATH directories are
  writable by the `demetra` account, so repository test code can plant an executable
  that a later root startup runs with container-root privileges.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-426** · **Category:** other (untrusted search path)
- **CodeRabbit ID:** `7f91eb29-e3dd-4ba0-bfd8-89dd5cd39e41`
- **Files (current):** `configs/docker-entrypoint.sh:6` (`id`), `:21` (`setpriv`)
- **Revalidation:** Confirmed. No `PATH` is pinned and `id`/`setpriv` are resolved by
  name. Note: a prior fix attempt was recorded in the scan as `fixStatus: failed`.

## Steps

1. Pin a trusted PATH at the very top of the entrypoint, before any command:
   `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.
2. Use absolute paths for privileged utilities in the root block:
   `/usr/bin/id`, `/usr/bin/setpriv`, `/bin/chown`, `/usr/bin/find`, `/bin/mkdir`,
   `/usr/bin/touch`.
3. Keep application-writable executable directories (e.g. anything under
   `/home/demetra`) out of the privileged PATH used by the root section.
4. Re-verify the previous failed fix by inspecting the current entrypoint and confirming
   no bare `id`/`setpriv` lookups remain in the root path.
