## Agent credits exhausted

The `{agent_name}` agent was rejected because the provider's credits or token
budget are exhausted (`{code}`). Retrying inside this run cannot help, so the
workflow stopped and the changes were rolled back.

### Error

```text
{error}
```

### What to do

Raise the provider's credit limit or point the agent at a model with an
available budget, then move the ticket back to `In Progress` to re-run.

{retry_hint}
