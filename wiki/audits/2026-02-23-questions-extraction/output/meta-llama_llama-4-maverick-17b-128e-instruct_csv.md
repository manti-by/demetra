# Extracted Questions

**Model:** `meta-llama/llama-4-maverick-17b-128e-instruct`  
**Parser:** `csv`  
**Count:** 23

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
12. reformatted to: 
13. Should the process manager monitor: All projects in `PROJECTS_PATH` (current behavior)
14. OR A specific list via a new env variable (e.g.
15. `PROCESS_MANAGER_PROJECTS`)?
16. Should spawned workflows run: In parallel (all at once)
17. OR Sequentially (one at a time)
18. OR With a max concurrency limit?
19. Should we track by: Database table (new `processed_tasks` table)
20. OR Just rely on Linear status being moved out of TODO (current workflow already does this)?
21. If a workflow fails
22. should we: Keep the task as "processing" and retry later
23. OR Move it back to TODO in Linear?
