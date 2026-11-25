## Agent rate limited

The `{agent_name}` agent was throttled by the model provider (`{code}`).
Demetra stopped the run after a provider rate limit, retrying with exponential
backoff only when the retry budget allowed it. The agent's edits remain in the
worktree and branch; when `WORKTREE_CLEANUP` is enabled, cleanup removes them
instead.

### Error

```text
{error}
```

### What to do

Wait for the provider's rate-limit window to reset, or lower the concurrency of
agent runs (`make deploy` and `make docker-up` scale workers with `--scale worker=4`),
then move the ticket back to `In Progress` to re-run.

{retry_hint}
