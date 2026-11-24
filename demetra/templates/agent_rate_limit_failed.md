## Agent rate limited

The `{agent_name}` agent was throttled by the model provider (`{code}`).
Demetra retried with exponential backoff until the retry budget was exhausted,
then stopped and rolled the changes back.

### Error

```text
{error}
```

### What to do

Wait for the provider's rate-limit window to reset, or lower the concurrency of
agent runs (`make deploy` and `make docker-up` scale workers with `--scale worker=4`),
then move the ticket back to `In Progress` to re-run.

{retry_hint}
