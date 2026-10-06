---
title: 'MNT-147 Wiki processes PR #70 — branch check and CI failure root cause'
date: 2026-08-07
type: code-review
status: resolved
session_id: opencode
services:
- wiki
- settings
- utils
- workflows
branch: mnt-147-wiki-processes
tickets:
- MNT-147
- MNT-155
tags:
- wiki
- code-review
- env
- ci
- regression
related:
- 2026-08-03-wiki-mcp-tools.md
- 2026-08-05-post-build-validation.md
- 2026-08-06-allowlist-review-fixes.md
---
# MNT-147 Wiki processes PR #70 — branch check and CI failure root cause

## TL;DR

PR #70 was MERGEABLE (UNSTABLE while CI failed). Root cause: `env_get_list` in `demetra/services/utils.py:249` returned `[]` instead of the default when the env var was unset, so CI (without `OPENCODE_REVIEW_MODELS`) produced an empty review-agent list and empty summarizer output. Fixed, merged as `cbd5b0e`.

---

## Findings

### 1. `env_get_list` returns `[]` instead of `default` when unset

**File:** `demetra/services/utils.py:249` — **Severity: High**

```python
def env_get_list(name: str, default: list) -> list:
    list_value = os.environ.get(name, "").split(",")
    return [x.strip() for x in list_value if x.strip()]
```

`os.environ.get(name, "")` → `""` → `[""]` → `[]`; default never used when unset.

Impacted (`demetra/settings.py`):
- `review_models` line 129 — unset → `[]` → `asyncio.gather(*[])` → empty `review_output` → `tests/test_workflows.py:1147` fails.
- `CORS_ALLOWED_ORIGINS` line 186 — same bug, blocks all browser origins unless explicitly set.
- `LINEAR_FILTER_LABELS` line 120 — latent (default `[]`).

**Fix:** `os.environ.get(name, ",".join(default))` or early-return when `name not in os.environ`.

### 2. PR marked CONFLICTING/DIRTY — resolved

**Severity: Resolved.** Head `f3edc44` was behind master after PR #71 merge (`f9c791f`). Merged master as `be8cde5`; GitHub now MERGEABLE.

### 3. CI fails on same review test

`tests/test_workflows.py:1147` (`test_run_review_agents_filters_thinking_prose`) — runs 31104702459/31104696195, same as finding 1. Repro: `env -u OPENCODE_REVIEW_MODELS pytest ...`.

### 4. CodeRabbit threads still open (3/16)

**Severity: Low/Medium.**
- `797d923e` — rate limit, docstring 66.67% vs 80%.
- `e6280678` — `settings.py:66-69` use named args for `read_int_env`/`env_get_int`; `env_get_int` should reject negatives.
- `ee8e79db` — 12 items: `logger.warning` `msg=` keyword; `queue.enqueue` named callable in `merge.py`/`rebase.py`.

---

## Summary table

| # | Severity | File | Description |
|---|----------|------|-------------|
| 1 | High | `demetra/services/utils.py:249` | `env_get_list` returns `[]` when unset |
| 2 | Blocker | PR #70 | CONFLICTING → MERGEABLE via `be8cde5` |
| 3 | High | `tests/test_workflows.py:1147` | CI failure caused by #1 |
| 4 | Low/Med | CodeRabbit threads | 3 unresolved |

---

## Branch state

- `HEAD` `be8cde5` matches PR #70 `headSha`; up to date with master.
- Diff `master...HEAD`: 21 files +2640/−251 (new `demetra/services/wiki.py` 1254 lines, `tests/test_wiki.py` 731 lines, etc.).

## Follow-ups

- Fix `env_get_list` → **Done** `f093e19` (`demetra/services/runtime/utils.py:272-273`).
- Merge PR #70 → **Done** `cbd5b0e`.
- CodeRabbit threads closed on merge.

## Consistency notes

- (2026-08-23) PR #70 merged 2026-08-07 07:14 UTC. Finding 1 fixed: `env_get_list` now `if value is None: return default` (`demetra/services/runtime/utils.py:261`).
- (2026-09-03) Default list transiently contained `minimax-m3` (2026-08-05 swap, reverted 2026-08-23); current `demetra/settings.py:148` is `[qwen3.7-plus, glm-5.2, kimi-k2.7-code]`. Bug fixed regardless.

## References

- Related: [[2026-08-03-wiki-mcp-tools]], [[2026-08-05-post-build-validation]], [[2026-08-06-allowlist-review-fixes]]
- External: https://github.com/manti-by/demetra/pull/70, [MNT-147](https://linear.app/mnt/issue/MNT-147)
