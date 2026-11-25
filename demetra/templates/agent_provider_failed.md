## Agent provider error

The `{agent_name}` agent failed with an ambiguous server-side error (`{code}`).
This signature has had unrelated causes (a workspace spending limit and a stale
session bound to a deleted worktree), so Demetra did not guess a retry: the
workflow stopped and the agent's edits remain in the worktree and branch. When
`WORKTREE_CLEANUP` is enabled, cleanup removes the worktree and branch instead.

### Error

```text
{error}
```

### What to do

Check the provider's status and billing, and confirm the agent session is not
stale, then move the ticket back to `In Progress` to re-run.

{retry_hint}
