# Extracted Questions

**Model:** `llama-3.1-8b-instant`  
**Parser:** `json`  
**Count:** 5

---

1. Create a new `process_manager.py` script that polls Linear TODO column every 5 minutes and spawns workflow processes for each new task.
2. Should the process manager monitor: All projects in `PROJECTS_PATH` (current behavior), OR a specific list via a new env variable (e.g., `PROCESS_MANAGER_PROJECTS`)?
3. Should spawned workflows run: In parallel (all at once), OR sequentially (one at a time), OR With a max concurrency limit?
4. Should we track by: Database table (new `processed_tasks` table), OR Just rely on Linear status being moved out of TODO (current workflow already does this)?
5. If a workflow fails, should we: Keep the task as 'processing' and retry later, OR Move it back to TODO in Linear?
