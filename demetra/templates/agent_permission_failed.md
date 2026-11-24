## Agent permission denied

The `{agent_name}` agent was denied access to the requested model or resource
(`{code}`). Retrying with the same credentials cannot help, so the workflow
stopped and the changes were rolled back.

### Error

```text
{error}
```

### What to do

Check that the provider credentials are valid and grant access to the configured
model, then move the ticket back to `In Progress` to re-run.

{retry_hint}
