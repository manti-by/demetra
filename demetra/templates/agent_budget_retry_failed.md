## Agent budget rejection

The `{agent_name}` agent's in-flight request was rejected because it needed
more budget than was available for that single request (`{code}`). Demetra
retried with the configured budget until no attempts remained, then stopped and
rolled the changes back.

### Error

```text
{error}
```

### What to do

Reduce the request size (for example a lower `max_tokens` or a smaller prompt)
or raise the provider's per-request budget, then move the ticket back to
`In Progress` to re-run.

{retry_hint}
