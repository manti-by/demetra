---
title: Fix wiki index lock not process-safe
date: 2026-08-28
type: implementation
status: resolved
session_id: ses_fbad8fd5affeytew8qRS0KDVpx
services: [wiki]
branch: mnt-189-release-v16-bugfixes
tickets: [MNT-189]
tags: [wiki, index, concurrency, flock, rq-workers, lock, lost-update]
related: [2026-08-07-split-wiki-service-into-subpackage.md, 2026-08-25-mnt-187-wiki-pages-not-generated.md]
---

# Fix wiki index lock not process-safe

## TL;DR

Wiki INDEX read-modify-write was only in-process serialized: `_INDEX_LOCK = asyncio.Lock()` plus `flock` taken only inside `_write_index_unlocked` after the read. Two RQ workers in separate processes could read the same `INDEX.md`, each append, and second `os.replace` clobbered the first (lost update). Fixed with `_index_lock` context manager holding flock for the whole read-modify-write; all four mutating entry points now run under it without re-acquiring flock in the write helper. Two-process repro confirms fix; 69 wiki tests pass.

## Overview

Module comment claimed cross-process serialization via `flock`, but flock was acquired at write time only — readers raced.

**Chain:** `asyncio.Lock` is process-local (RQ workers are separate processes) → `flock` only in `_write_index_unlocked` after read → two workers read same base, compute `updated` independently, second `os.replace` overwrites first.

## Fix

`demetra/services/wiki/index.py:43-67` — added `asynccontextmanager` holding both locks for the whole operation:
```python
@asynccontextmanager
async def _index_lock(target: Path) -> AsyncIterator[None]:
    lock_path = target.with_suffix(f"{target.suffix}.lock")
    async with _INDEX_LOCK:
        fd = await asyncio.to_thread(_acquire_flock, lock_path)
        try:
            yield
        finally:
            await asyncio.to_thread(_release_flock, fd)
```

`demetra/services/wiki/index.py` — `write_index`, `prune_index_pages`, `patch_index`, `regenerate_by_topic` now wrap read-modify-write in `async with _index_lock(target):` (was `_INDEX_LOCK`). `_write_index_unlocked` no longer acquires flock (caller holds it; re-acquiring same-process on second fd would block). Docstrings updated.

## Test Results

- `uv run pytest tests/test_wiki.py -q` — **69 passed**; `ruff check` / `ty check` clean
- Two-subprocess repro: concurrent `patch_index` in two `uv run python` processes against shared INDEX — both entries survived (4 matches = 2 pages × `## Pages` + `## By topic`)

## Follow-ups

- None.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-25-mnt-187-wiki-pages-not-generated]]
