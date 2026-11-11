---
title: "MNT-176: Bump version error fix"
date: 2026-08-21
type: implementation
status: resolved
session_id: "-"
services: [workflows]
branch: mnt-176-bump-version-error
tickets: [MNT-176]
tags: [version, bump, pyproject, bug-fix]
related: [2026-09-08-docstring-mcp-search.md, 2026-06-25-update-project-version.md]
---

# MNT-176: Bump version error fix

## TL;DR

`bump_project_version` incorrectly bumped major for Epic-labeled tickets (`1.x.y → 2.0.0`); rule is major is manual-only. Removed `is_epic` param and major-bump branch — now always bumps minor (preserves major) — deleted `EPIC_LABEL`/`is_epic_label`, updated call site and tests. Contract later superseded by [[2026-09-08-docstring-mcp-search]] (explicit `is_major`/`is_minor`/`is_patch` flags, default patch).

## Overview

Auto-bump was major-on-Epic / minor-otherwise; now always minor with major preserved for manual releases.

## Service fix

`demetra/services/runtime/project.py` — removed `is_epic` from `bump_project_version(target_path: Path) -> str | None`:
```python
# before: if is_epic: f"{major+1}.0.0{suffix}" else: f"{major}.{minor+1}.0{suffix}"
# after:  f"{major}.{minor+1}.0{suffix}"
```
Deleted `EPIC_LABEL` and `is_epic_label(labels)`. Docstring updated: minor bumped on every workflow, major manual-only.

## Workflow call site

`demetra/workflows/build.py` — dropped `is_epic` plumbing:
```python
# before: from project import bump_project_version, is_epic_label; bump_project_version(target_path=..., is_epic=is_epic_label(...))
# after:  from project import bump_project_version; bump_project_version(target_path=context.worktree_path)
```
`is_version_updated` guard unchanged.

## Tests

- `tests/test_project.py` — removed `TestIsEpicLabel`/`test_major_bump`, dropped `is_epic=False` kwargs, added `test_major_version_preserved` (`2.14.1 → 2.15.0`)
- `tests/test_workflows.py` — removed `mock_is_epic_label` fixture/usages
- `tests/test_more_edge_cases.py` — unchanged

## Test Results

`pytest tests/test_project.py tests/test_workflows.py tests/test_more_edge_cases.py` pass; `ruff check .` and `ty check` clean.

## Follow-ups

- None.

## Consistency fix (2026-08-25)

- Frontmatter `title` quoted to escape `:`.

## Consistency note (2026-09-11, Consistency Agent)

- Superseded by [[2026-09-08-docstring-mcp-search]] (`dd4f152`): `bump_project_version` now takes `is_major`/`is_minor`/`is_patch` (default `is_patch=True` → patch, not minor). Always-minor contract above is stale.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-06-25-update-project-version]], [[2026-09-08-docstring-mcp-search]]
- External: [MNT-176 — Bump version error (Linear)](https://linear.app/mnt/issue/MNT-176)

> **Consistency note (2026-11-11, Consistency Agent):** The body above still describes a minor bump; since the 2026-09-08 rework `bump_project_version(target_path, is_major=False, is_minor=False, is_patch=True)` defaults to a **patch** bump (`demetra/services/runtime/project.py:331-332`) and the build workflow calls it with no flag (`demetra/workflows/build.py:234`), so the auto-bump increments the patch component. This is the resolved **Q-001**; the `is_epic` rule removed here is still gone.
