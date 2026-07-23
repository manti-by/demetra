# Extracted Questions

**Model:** `meta-llama/llama-4-maverick-17b-128e-instruct`  
**Parser:** `json`  
**Count:** 4

---

1. Should the process manager monitor: All projects in `PROJECTS_PATH` (current behavior), OR A specific list via a new env variable (e.g., `PROCESS_MANAGER_PROJECTS`)?
2. Should spawned workflows run: In parallel (all at once), OR Sequentially (one at a time), OR With a max concurrency limit?
3. Should we track by: Database table (new `processed_tasks` table), OR Just rely on Linear status being moved out of TODO (current workflow already does this)?
4. If a workflow fails, should we: Keep the task as "processing" and retry later, OR Move it back to TODO in Linear?
