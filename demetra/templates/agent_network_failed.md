## Agent network failure

The `{agent_name}` agent could not reach the model provider: every attempt was
rejected by a transient network error, so the workflow was stopped and the
changes rolled back.

### Error

```text
{error}
```

### Possible causes

- The connection was reset while the request was in flight (`ECONNRESET`), or
  DNS/connectivity was briefly unavailable.
- A proxy, VPN or firewall is dropping long-running agent requests.

Please check connectivity from the host running Demetra, then move the ticket
back to `In Progress` to re-run the workflow.
