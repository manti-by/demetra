## Build agent failed

The build agent exited with an error before producing any changes, so the
workflow was stopped and the changes rolled back.

### Error

```
{error}
```

### Possible causes

- The OpenCode workspace may have reached its monthly spending limit; check the
  billing page at https://opencode.ai/workspace and raise the limit, or switch
  the build model to a free one.
- The build agent may have hit a transient server error; re-run the workflow to
  confirm.

Please investigate, then move the ticket back to `In Progress` to re-run the
workflow.