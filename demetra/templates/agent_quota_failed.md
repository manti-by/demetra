## Agent credits exhausted

The `{agent_name}` agent was rejected because the provider's credits or token
budget are exhausted (`{code}`). Retrying inside this run cannot help, so the
workflow stopped and the agent's edits remain in the worktree and branch. When
`WORKTREE_CLEANUP` is enabled, cleanup removes the worktree and branch instead.

### Error

```text
{error}
```

### What to do

Raise the provider's credit limit or point the agent at a model with an
available budget, then move the ticket back to `In Progress` to re-run.

{retry_hint}
