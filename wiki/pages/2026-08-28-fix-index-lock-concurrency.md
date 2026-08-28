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

The wiki INDEX read-modify-write was only serialized in-process: `_INDEX_LOCK` is an `asyncio.Lock()` (process-local), and the cross-process `flock` was taken only inside `_write_index_unlocked` — after the read. Two RQ workers in separate processes could both read the same `INDEX.md`, each append their own page entry, and the second `os.replace` clobbered the first (lost update). Fixed by adding an `_index_lock` async context manager that holds the flock for the whole read-modify-write; all four mutating entry points (`write_index`, `prune_index_pages`, `patch_index`, `regenerate_by_topic`) now run under it, and the write helper no longer re-acquires the flock (which would have nested and deadlocked). Verified with a two-subprocess concurrency repro and the full wiki suite.

---

## Overview

**Symptom:** the module comment on `_INDEX_LOCK` claimed "Cross-process writers (RQ workers) are additionally serialized by an flock", but the flock was acquired inside `_write_index_unlocked`, which runs only at the write. The read-modify-write functions read the INDEX first and only then entered the flock-protected write, so two workers could each read the same content and one write was lost.

**Root cause chain:**

1. `_INDEX_LOCK = asyncio.Lock()` (`demetra/services/wiki/index.py`) guards only coroutines in the same process — RQ workers are separate processes, so it provides no mutual exclusion there.
2. `fcntl.flock` was taken only in `_write_index_unlocked`, after the caller had already read the INDEX.
3. Two workers therefore both read the same INDEX, each computed an `updated` content from the same base, and the second `os.replace` overwrote the first worker's entry.

## Step 1 — Add _index_lock context manager

**File:** `demetra/services/wiki/index.py:43-67`

Added an `asynccontextmanager` that acquires the process-local `_INDEX_LOCK` and then the cross-process flock on `INDEX.md.lock`, holding both for the duration of the caller's read-modify-write:

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

## Step 2 — Route all mutating entry points through it

**File:** `demetra/services/wiki/index.py`

`write_index`, `prune_index_pages`, `patch_index` and `regenerate_by_topic` now wrap their whole read-modify-write in `async with _index_lock(target):` instead of `_INDEX_LOCK`. `_write_index_unlocked` keeps only the tmp+replace write; its own flock acquisition was removed because the caller now holds the flock, and re-acquiring it from the same process on a second fd would block (flock is per open-file-description). Docstrings updated to reference `_index_lock`.

## Test Results

- `uv run pytest tests/test_wiki.py -q` — **69 passed**.
- `uv run ruff check demetra/services/wiki/index.py` — clean.
- `uv run ty check demetra/services/wiki/index.py` — clean.
- Two-subprocess repro: ran `patch_index` concurrently in two separate `uv run python` processes against a shared INDEX; both page entries survived (4 index matches = 2 pages × `## Pages` + `## By topic`), confirming the cross-process flock now serializes the read-modify-write.

---

## Follow-ups

- None.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-25-mnt-187-wiki-pages-not-generated]]