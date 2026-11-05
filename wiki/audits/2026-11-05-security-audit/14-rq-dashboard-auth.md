# 14 — RQ dashboard exposed without authentication

## Summary

- **Title:** Administrative queue dashboard reachable by unauthenticated callers
- **Problem:** The deployment launches `rq-dashboard` without `--username`/`--password`
  and publishes it on `0.0.0.0:9181`, then proxies `/rq/` to it through nginx.
  Unauthenticated callers can inspect, delete, and requeue application workflow jobs in
  the same Redis database the workers use. The directly published port also bypasses
  any control added only at the proxy.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-306** · **Category:** broken_auth
- **CodeRabbit ID:** `3482822c-0ff9-42c0-b8ce-d659f00e6dc0`
- **Files (current):** `docker-compose.yaml:123-144` (`rq-dashboard` service),
  `configs/nginx.conf:34-37` (`/rq/` location)
- **Revalidation:** Confirmed. The dashboard command has no auth flags and publishes
  `9181:9181`; nginx proxies `/rq/` to `127.0.0.1:9181`. (Scanner assumption A3: the
  shipped launch/proxy config is used without extra dashboard credentials.)

## Steps

1. Add operator authentication to the dashboard command using
   `--username "${RQ_DASHBOARD_USERNAME}" --password "${RQ_DASHBOARD_PASSWORD}"`,
   sourced from `.env.docker`/environment with no insecure default.
2. Bind the dashboard to `127.0.0.1` and remove the direct `9181:9181` port publication
   so the authenticated nginx `/rq/` route is the only entry point.
3. Add `auth_basic` (or an equivalent origin/IP restriction) on the nginx `/rq/`
   location as defense in depth.
4. Document the new required env vars and update any deployment docs/tests that assume
   an open dashboard.
