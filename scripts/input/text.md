## Implementation Plan: Process Manager

### Overview

Create a new `process_manager.py` script that polls Linear TODO column every 5 minutes and spawns workflow processes for each new task.

### Components

#### 1\. New Script: `process_manager.py` (in project root)

* Async infinite loop that runs every 5 minutes
* Discover projects from `PROJECTS_PATH` (existing behavior)
* For each project, query Linear TODO issues using existing `get_todo_issues()`
* Track already-processed tasks in database (new table or reuse sessions table)
* Spawn workflow processes asynchronously using `asyncio.create_subprocess_exec`
* Each workflow runs: `uv run main.py --project-name <project>`

#### 2\. Database Tracking

* Add a `processed_tasks` table to track task IDs that have been picked up (to avoid re-processing)
* When a task is picked up, mark it as processed before spawning the workflow

#### 3\. Systemd Service

* Create `demetra-process-manager.service` in project root
* Standard systemd service configuration with:
  * `Type=simple`
  * `Restart=always`
  * Environment variables via `.env` or systemd env file

#### 4\. Tests

* Test the polling loop logic
* Test task discovery and filtering
* Test subprocess spawning
* Test database tracking

---

## Clarifying Questions

1. **Project Discovery**: Should the process manager monitor:
   * All projects in `PROJECTS_PATH` (current behavior), OR
   * A specific list via a new env variable (e.g., `PROCESS_MANAGER_PROJECTS`)?
2. **Parallelism**: Should spawned workflows run:
   * In parallel (all at once), OR
   * Sequentially (one at a time), OR
   * With a max concurrency limit?
3. **Already-processed tasks**: Should we track by:
   * Database table (new `processed_tasks` table), OR
   * Just rely on Linear status being moved out of TODO (current workflow already does this)?

   Note: If we rely on Linear status, there's a race condition window between checking and the workflow moving the task.
4. **Error handling**: If a workflow fails, should we:
   * Keep the task as "processing" and retry later, OR
   * Move it back to TODO in Linear?

---
