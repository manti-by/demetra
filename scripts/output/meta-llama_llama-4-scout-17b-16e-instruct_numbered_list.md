# Extracted Questions

**Model:** `meta-llama/llama-4-scout-17b-16e-instruct`  
**Parser:** `numbered_list`  
**Count:** 13

---

1. **Project Discovery**: Should the process manager monitor:
2. * All projects in `PROJECTS_PATH` (current behavior), OR
3. * A specific list via a new env variable (e.g., `PROCESS_MANAGER_PROJECTS`)?
4. **Parallelism**: Should spawned workflows run:
5. * In parallel (all at once), OR
6. * Sequentially (one at a time), OR
7. * With a max concurrency limit?
8. **Already-processed tasks**: Should we track by:
9. * Database table (new `processed_tasks` table), OR
10. * Just rely on Linear status being moved out of TODO (current workflow already does this)?
11. **Error handling**: If a workflow fails, should we:
12. * Keep the task as "processing" and retry later, OR
13. * Move it back to TODO in Linear?
