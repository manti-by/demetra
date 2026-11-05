# 08 — Log injection via waitlist email control characters

## Summary

- **Title:** Stored signup email with embedded line breaks corrupts approval output
- **Problem:** `normalize_email` only strips and lowercases, so a signup email can
  contain CR/LF control characters. When an operator approves the entry,
  `send_approval_email` interpolates the stored recipient into an approval message
  without encoding line breaks, allowing attacker-controlled text to appear as
  additional application log/console records.
- **Date:** 2026-11-05
- **Severity:** low · **CWE-117** · **Category:** other (log injection)
- **CodeRabbit ID:** `83ab3334-b4e7-4e28-91fe-3ef6eb8a7967`
- **Files (current):** `demetra/services/auth/allowlist.py:30-39` (`normalize_email`),
  `demetra/services/auth/waitlist.py:53-83` (`send_approval_email`)
- **Revalidation:** Confirmed. `normalize_email` returns `value.strip().lower()` with no
  control-character filtering, and `send_approval_email` interpolates `recipient`
  directly into the printed message.

## Steps

1. In `normalize_email` (`demetra/services/auth/allowlist.py`), strip or reject CR/LF
   and other control characters (e.g. `re.sub(r"[\r\n\x00-\x1f\x7f]+", " ", value)`
   or raise on detection).
2. Tighten signup email validation in `signup_with_password`
   (`demetra/services/auth/sessions.py:100-103`) beyond the bare `"@" in email` check
   to reject control characters and malformed addresses before they reach storage.
3. Defensively encode the recipient in `send_approval_email`
   (`demetra/services/auth/waitlist.py:79-82`) before interpolation (replace CR/LF with
   escaped forms) so one event can never produce multiple apparent records.
4. Add tests: a signup email containing `\r\n` is rejected or sanitised, and the
   approval message contains no raw line breaks.
