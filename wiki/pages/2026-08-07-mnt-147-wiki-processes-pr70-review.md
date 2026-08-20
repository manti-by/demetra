---
title: "MNT-147 Wiki processes PR #70 — branch check and CI failure root cause"
date: 2026-08-07
type: code-review
status: resolved
session_id: opencode
services: [wiki, settings, utils, workflows]
branch: mnt-147-wiki-processes
tickets: [MNT-147, MNT-155]
tags: [wiki, code-review, env, ci, regression]
related: [2026-08-03-wiki-mcp-tools.md, 2026-08-06-allowlist-review-fixes.md]
---

# MNT-147 Wiki processes PR #70 — branch check and CI failure root cause

## TL;DR

PR #70 (mnt-147-wiki-processes) merged after fixing an `env_get_list` regression in `demetra/services/runtime/utils.py` that returned `[]` instead of the default when `OPENCODE_REVIEW_MODELS` was unset — causing CI failure on `test_run_review_agents_filters_thinking_prose` with an empty review-agent list. The wiki subpackage split from the same PR is live on `master`.

---

## Findings

### 1. `env_get_list` returns `[]` instead of `default` when the variable is unset

**File:** demetra/services/utils.py:249

```python
def env_get_list(name: str, default: list) -> list:
    try:
        list_value = os.environ.get(name, "").split(",")
        return [x.strip() for x in list_value if x.strip()]
    except ValueError:
        pass
    return default
```

**Severity:** High — CI regression and production behavior change.

`os.environ.get(name, "")` yields `""` when unset, which splits to `[""]` and filters to `[]` — the `default` is never used for the unset case. Confirmed live: `env_get_list("FOO", ["a", "b"])` returns `[]` with `FOO` unset.

**Impacted call sites** (demetra/settings.py):

- `"review_models": env_get_list("OPENCODE_REVIEW_MODELS", ["opencode-go/qwen3.7-plus", "opencode-go/glm-5.2", "opencode-go/minimax-m3"])` — line 129. With the var unset the old code (`os.environ.get("OPENCODE_REVIEW_MODELS", "qwen3.7-plus,glm-5.2,minimax-m3").split(",")`) returned the 3 defaults; the refactor returns `[]`. In CI the var is unset → empty review agent list → `asyncio.gather(*[])` → empty `review_output` → `test_run_review_agents_filters_thinking_prose` fails on `tests/test_workflows.py:1147`.
- `CORS_ALLOWED_ORIGINS = env_get_list("CORS_ALLOWED_ORIGINS", ["http://localhost:5173", "http://localhost:8000"])` — line 186. Same bug: unset → `[]` → CORS blocks all browser origins in production unless the var is explicitly set.
- `LINEAR_FILTER_LABELS` — line 120, default `[]`, so the bug is latent only.

**Fix:** use the default as the fallback string, e.g. `os.environ.get(name, ",".join(default)).split(",")`, or early-return `default` when `name not in os.environ`.

### 2. GitHub marked PR #70 as CONFLICTING / DIRTY (now resolved)

**File:** PR manti-by/demetra#70 (headSha `be8cde5`, baseSha `99b5880`)

**Severity:** Resolved — was Blocker.

The PR head was the branch HEAD (`f3edc44`), behind master after PR #71 (MNT-155 allowlist merged via `f9c791f`). Git Flow requires the branch to be rebased/merged on latest master before it can merge. The master merge is now committed and pushed as `be8cde5`; GitHub reports the PR MERGEABLE. The remaining check failures are finding 3, caused by finding 1.

### 3. Both CI "Run checks" runs fail on the same review test

**File:** tests/test_workflows.py:1147 (`TestWorkflowReview::test_run_review_agents_filters_thinking_prose`)

**Severity:** High — directly caused by finding 1. Runs 31104702459 and 31104696195 both assert `"Looking at the staged changes..." in ''`. Reproduced locally with `env -u OPENCODE_REVIEW_MODELS uv run pytest tests/test_workflows.py::TestWorkflowReview::test_run_review_agents_filters_thinking_prose`; passes with the var set.

### 4. CodeRabbit review threads still open

**Severity:** Low/Medium — 3 unresolved of 16 threads:

- Thread `797d923e` — review rate limit reached mid-run; noted docstring coverage 66.67% vs 80% target.
- Thread `e6280678` — settings.py L66-69: use named arguments for `read_int_env`/`env_get_int` calls (WIKI_GROQ_BUDGET_FILES, WIKI_GROQ_BUDGET_LINES, WIKI_DIFF_HUNK_CAP, WIKI_BUILD_PLAN_CAP); also `env_get_int` should reject negative values (current `non_negative_int` helper exists but is not used there).
- Thread `ee8e79db` — 12 actionable items (5 nitpicks + 7 inline): `logger.warning` should use `msg=` keyword; `queue.enqueue` should use a named callable in `demetra/workflows/merge.py` and `rebase.py`.

---

## Summary table

| # | Severity | Repo | File | Description |
|---|----------|------|------|-------------|
| 1 | High | demetra | demetra/services/utils.py:249 | `env_get_list` returns `[]` instead of default when env var unset |
| 2 | Blocker | GitHub | PR #70 | CI checks failing on #1; merge committed as `be8cde5`, GitHub reports MERGEABLE |
| 3 | High | demetra | tests/test_workflows.py:1147 | CI failure caused by #1; reproduces with `env -u OPENCODE_REVIEW_MODELS` |
| 4 | Low/Med | linear | CodeRabbit threads | 3 unresolved: named args, `msg=`, enqueue callable, docstring coverage |

---

## Branch state

- `HEAD`: `be8cde5` "Merge branch 'master' into mnt-147-wiki-processes" (matches PR #70 headSha).
- Branch-only commits: `2bed1c7` (MNT-147: Wiki processes), `618184a` (Fix review findings), `bcbe0dc` (Isolate wiki tests), `f3edc44` (merge), `be8cde5` (merge).
- Master-only since last sync: none — branch is up to date with master.
- Diff `master...HEAD`: 21 files, +2640/−251 (new `demetra/services/wiki.py` 1254 lines, `tests/test_wiki.py` 731 lines, this review page, `demetra/prompts/summarize_session.md`, groq/utils/settings/tools/wiki/merge/rebase changes).
- Master merge (MNT-155) committed as `be8cde5` and pushed; PR #70 is no longer CONFLICTING.

## Follow-ups

- Fix `env_get_list` unset handling and re-run the two CI checks.
- Once CI passes, PR #70 is ready to merge (branch is up to date with master).
- Address the 3 open CodeRabbit threads (or mark resolved).
- MNT-147 Linear ticket is In Review — will move to Done on merge.

## Consistency note (2026-08-20)

PR #70 merged; the wiki subpackage split landed on `master` (see [[2026-08-07-split-wiki-service-into-subpackage]]). The `env_get_list` unset-handling regression was fixed in `demetra/services/runtime/utils.py` (same session as [[2026-08-09-wiki-fixes-and-test-optimization]]). The default third `OPENCODE_REVIEW_MODELS` entry on current `master` is `opencode-go/kimi-k2.7-code`, not `minimax-m3` (see [[2026-08-05-post-build-validation]] consistency note).

## References

- Related: [[2026-08-06-allowlist-review-fixes]], [[2026-08-03-wiki-mcp-tools]]
- External: https://github.com/manti-by/demetra/pull/70, [MNT-147](https://linear.app/mnt/issue/MNT-147)
