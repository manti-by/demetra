# Extracted Questions

**Model:** `qwen/qwen3-32b`  
**Parser:** `numbered_list`  
**Count:** 22

---

1. <think>
2. Okay, let's see. The user wants me to extract all the questions from the provided markdown text. The instructions say to return them as a numbered list, one per line, preserving the original wording exactly. I need to make sure I don't split any choice questions that have "or", "and", etc. into multiple items.
3. First, I'll look through the text. The main section with questions is under "Clarifying Questions". There are four numbered questions there. Let me check each one.
4. The first question is about project discovery, asking whether to monitor all projects or a specific list via an env variable. That's one question, so it should be number 1.
5. The second question is about parallelism, with three options. It's a single question with multiple choices, so it stays as number 2.
6. The third question is about tracking already-processed tasks, with two options. It's one question, so number 3. The note is part of the question but doesn't split it into two.
7. The fourth question is about error handling, with two options. That's number 4.
8. I need to make sure I don't include any other parts of the text. The rest of the document is the implementation plan and components, which don't have questions. The "Clarifying Questions" section is the only part with the numbered questions. So the final list should have four items, each as they are, numbered 1 to 4.
9. </think>
10. **Project Discovery**: Should the process manager monitor:
11. * All projects in `PROJECTS_PATH` (current behavior), OR
12. * A specific list via a new env variable (e.g., `PROCESS_MANAGER_PROJECTS`)?
13. **Parallelism**: Should spawned workflows run:
14. * In parallel (all at once), OR
15. * Sequentially (one at a time), OR
16. * With a max concurrency limit?
17. **Already-processed tasks**: Should we track by:
18. * Database table (new `processed_tasks` table), OR
19. * Just rely on Linear status being moved out of TODO (current workflow already does this)?
20. **Error handling**: If a workflow fails, should we:
21. * Keep the task as "processing" and retry later, OR
22. * Move it back to TODO in Linear?
