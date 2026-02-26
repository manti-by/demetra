# Extracted Questions

**Model:** `llama-3.1-8b-instant`  
**Parser:** `numbered_list`  
**Count:** 4

---

1. Should the process manager monitor: All projects in `PROJECTS_PATH` (current behavior), OR a specific list via a new env variable (e.g., `PROCESS_MANAGER_PROJECTS`)?
2. Should spawned workflows run: In parallel (all at once), OR sequentially (one at a time), OR with a max concurrency limit?
3. Should we track already-processed tasks by: Database table (new `processed_tasks` table), OR just rely on Linear status being moved out of TODO (current workflow already does this)?
4. If a workflow fails, should we: Keep the task as "processing" and retry later, OR move it back to TODO in Linear?
