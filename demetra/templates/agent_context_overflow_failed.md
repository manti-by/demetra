## Agent context overflow

The `{agent_name}` agent's input exceeded the model's context window (`{code}`).
Repeating the same request will overflow again, so the workflow stopped and the
changes were rolled back.

### Error

```text
{error}
```

### What to do

Reduce the context passed to the agent (a smaller task description or fewer
comments), or compact the resumed session earlier. {recovery}

{retry_hint}
