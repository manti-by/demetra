# Extracted Questions

**Model:** `moonshotai/kimi-k2-instruct-0905`  
**Parser:** `csv`  
**Count:** 11

---

1. Should the process manager monitor: All projects in `PROJECTS_PATH` (current behavior)
2. OR A specific list via a new env variable (e.g.
3. `PROCESS_MANAGER_PROJECTS`)?
4. Should spawned workflows run: In parallel (all at once)
5. OR Sequentially (one at a time)
6. OR With a max concurrency limit?
7. Should we track by: Database table (new `processed_tasks` table)
8. OR Just rely on Linear status being moved out of TODO (current workflow already does this)?
9. If a workflow fails
10. should we: Keep the task as "processing" and retry later
11. OR Move it back to TODO in Linear?
