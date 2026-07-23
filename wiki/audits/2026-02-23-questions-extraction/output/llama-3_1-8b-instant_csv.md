# Extracted Questions

**Model:** `llama-3.1-8b-instant`  
**Parser:** `csv`  
**Count:** 11

---

1. 1. Should the process manager monitor: All projects in `PROJECTS_PATH` (current behavior)
2. OR a specific list via a new env variable (e.g.
3. `PROCESS_MANAGER_PROJECTS`)?
4. 2. Should spawned workflows run: In parallel (all at once)
5. OR sequentially (one at a time)
6. OR with a max concurrency limit?
7. 3. Should we track already-processed tasks by: Database table (new `processed_tasks` table)
8. OR just rely on Linear status being moved out of TODO (current workflow already does this)?
9. 4. If a workflow fails
10. should we: Keep the task as "processing" and retry later
11. OR move it back to TODO in Linear?
