# Extracted Questions

**Model:** `qwen/qwen3-32b`  
**Parser:** `csv`  
**Count:** 38

---

1. <think>
2. Okay
3. let's see. The user wants me to extract all the questions from the provided markdown text. The instructions say to return them as a numbered list
4. one per line
5. preserving the original wording exactly. Also
6. don't split choice questions even if they have "or" or "and".
7. First
8. I'll look through the text. The main section with questions is under "Clarifying Questions". There are four numbered questions there. Let me check each one.
9. 1. The first question is about project discovery
10. asking whether to monitor all projects or a specific list via an env variable. That's one question.
11. 2. The second is about parallelism
12. with three options. It's a single question even though there are three choices.
13. 3. The third question is about tracking processed tasks
14. comparing a database table versus relying on Linear status. The note mentions a race condition
15. but the question itself is one item.
16. 4. The fourth question is about error handling
17. with two options. Again
18. one question.
19. I need to make sure I don't split any of these into multiple items. For example
20. the second question has three options but is still one question. Also
21. check if there are any other questions elsewhere in the text. The rest of the document is about the implementation plan and components
22. which don't have questions. So the four questions under "Clarifying Questions" are the only ones. Let me list them exactly as they are
23. preserving the original wording
24. including the asterisks and formatting. The user wants the questions as a plain numbered list
25. so I'll just list them as they are
26. each on a separate line with numbers.
27. </think>
28. 1. **Project Discovery**: Should the process manager monitor: * All projects in `PROJECTS_PATH` (current behavior)
29. OR * A specific list via a new env variable (e.g.
30. `PROCESS_MANAGER_PROJECTS`)?  
31. 2. **Parallelism**: Should spawned workflows run: * In parallel (all at once)
32. OR * Sequentially (one at a time)
33. OR * With a max concurrency limit?  
34. 3. **Already-processed tasks**: Should we track by: * Database table (new `processed_tasks` table)
35. OR * Just rely on Linear status being moved out of TODO (current workflow already does this)?  
36. 4. **Error handling**: If a workflow fails
37. should we: * Keep the task as "processing" and retry later
38. OR * Move it back to TODO in Linear?
