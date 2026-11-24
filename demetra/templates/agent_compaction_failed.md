## Agent compaction unavailable

The `{agent_name}` agent failed because its context needed compaction but this
OpenCode version has no compaction command (`{code}`). Retrying the same run
will hit the same limit, so the workflow stopped and the changes were rolled
back.

### Error

```text
{error}
```

### What to do

Use an OpenCode version that supports session compaction, or reduce the context
passed to the agent (a smaller build plan or a fresh session). {recovery}

{retry_hint}
