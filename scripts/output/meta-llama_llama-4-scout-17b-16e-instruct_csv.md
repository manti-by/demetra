# Extracted Questions

**Model:** `meta-llama/llama-4-scout-17b-16e-instruct`  
**Parser:** `csv`  
**Count:** 14

---

1. 1. Project Discovery: Should the process manager monitor:   * All projects in `PROJECTS_PATH` (current behavior)
2. OR   * A specific list via a new env variable (e.g.
3. `PROCESS_MANAGER_PROJECTS`)?
4. 
5. 2. Parallelism: Should spawned workflows run:   * In parallel (all at once)
6. OR   * Sequentially (one at a time)
7. OR   * With a max concurrency limit?
8. 
9. 3. Already-processed tasks: Should we track by:   * Database table (new `processed_tasks` table)
10. OR   * Just rely on Linear status being moved out of TODO (current workflow already does this)?
11. 
12. 4. Error handling: If a workflow fails
13. should we:   * Keep the task as "processing" and retry later
14. OR   * Move it back to TODO in Linear?
