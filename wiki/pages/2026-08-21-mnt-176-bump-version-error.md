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
related: [2026-06-25-update-project-version.md]
---

# MNT-176: Bump version error fix

## TL;DR

`bump_project_version` was bumping the **major** version for Epic-labeled tickets (`1.x.y → 2.0.0`), which contradicted the rule that major is bumped manually only. Removed the `is_epic` parameter and the major-bump branch: the function now always bumps the **minor** version and preserves the major. The now-unused `is_epic_label` helper and `EPIC_LABEL` constant were deleted, and the call site, tests, and the original MNT-116 wiki page were updated to match.

---

## Overview

The contract change is a single axis: the auto-bump used to be **major-on-Epic / minor-otherwise**; it is now **always minor**, with the major version preserved and reserved for manual release bumps. This matches the "never bump major automatically" rule.

## Step 1 — Service fix

**File:** `demetra/services/runtime/project.py`

Removed `is_epic` from the signature and collapsed the conditional into a single minor increment:

Before:

```python
def bump_project_version(target_path: Path, is_epic: bool = False) -> str | None:
    ...
    if is_epic:
        new_version = f"{major + 1}.0.0{suffix}"
    else:
        new_version = f"{major}.{minor + 1}.0{suffix}"
```

After:

```python
def bump_project_version(target_path: Path) -> str | None:
    ...
    new_version = f"{major}.{minor + 1}.0{suffix}"
```

Also deleted the `EPIC_LABEL` constant and the `is_epic_label(labels)` helper from the same module — the only caller was the build workflow (see Step 2), so they became dead code. The docstring now states that the minor version is bumped on every feature/bugfix workflow and the major is preserved and manual-only.

## Step 2 — Workflow call site

**File:** `demetra/workflows/build.py`

Dropped the `is_epic` plumbing at the bump call:

Before:

```python
from demetra.services.runtime.project import bump_project_version, is_epic_label
...
new_version = bump_project_version(
    target_path=context.worktree_path,
    is_epic=is_epic_label(labels=context.linear_task.labels),
)
```

After:

```python
from demetra.services.runtime.project import bump_project_version
...
new_version = bump_project_version(target_path=context.worktree_path)
```

The `is_version_updated` guard that runs the bump once per workflow is unchanged.

## Step 3 — Tests

- `tests/test_project.py`: removed `TestIsEpicLabel` (helper is gone) and `test_major_bump` (major path is gone); dropped the `is_epic=False` kwarg from the remaining `TestBumpProjectVersion` methods; added `test_major_version_preserved` to pin the new contract (`2.14.1 → 2.15.0`).
- `tests/test_workflows.py`: removed the `mock_is_epic_label` fixture and its three usages in the build-step tests.
- `tests/test_more_edge_cases.py`: unchanged — it patches `demetra.workflows.build.bump_project_version`, which still resolves.

## Test Results

`pytest tests/test_project.py tests/test_workflows.py tests/test_more_edge_cases.py` all pass; `ruff check .` and `ty check` clean.

---

## Follow-ups

None.

## References

- Related: [[2026-06-25-update-project-version]]
- External: [MNT-176 — Bump version error (Linear)](https://linear.app/mnt/issue/MNT-176)
