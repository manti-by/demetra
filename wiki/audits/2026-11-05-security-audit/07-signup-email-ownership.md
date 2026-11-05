# 07 — Password signup skips email-ownership verification

## Summary

- **Title:** Allowlisted email can be claimed by anyone who knows it
- **Problem:** `signup_with_password` creates an active account from a
  caller-supplied allowlisted email and issues a JWT immediately, without proving the
  caller owns that address. Someone who knows an approved, unregistered address can
  set its password and obtain the access intended for that identity.
- **Date:** 2026-11-05
- **Severity:** low · **CWE-287** · **Category:** broken_auth
- **CodeRabbit ID:** `866e7582-6019-443d-8f82-34dab3aabe0e`
- **Files (current):** `demetra/services/auth/sessions.py:81-140`
  (`signup_with_password`)
- **Revalidation:** Confirmed. The flow checks the allowlist then creates the user and
  session (`sessions.py:113-124`) with no mailbox-verification or invitation step.

## Steps

1. Introduce a single-use verification token (or invitation token) bound to the
   approved email address; store it in a new `email_verifications` table (migration
   `create_email_verifications_table`).
2. Change `signup_with_password` to create the user in a *pending* state (or create the
   token only) and return a "verify your email" response instead of issuing a session.
3. Add a `POST /api/v1/auth/verify-email` (or extend signup) endpoint that consumes the
   token, activates the account, and only then issues the first session.
4. Keep the GitHub OAuth path unchanged (it is already bound to an authenticated GitHub
   identity).
5. Add tests: signup returns pending; verifying with a bad/expired token fails;
   verifying with the correct token activates and issues a session.
