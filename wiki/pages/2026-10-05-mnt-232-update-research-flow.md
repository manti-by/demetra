---
title: 'MNT-232: Update research flow'
date: '2026-10-05'
type: implementation
status: resolved
session_id: ses_ef2314203ffe3rEkhgo1cOltPV
services: [linear, workflows/research]
branch: mnt-232-update-research-flow
tickets: [MNT-232]
tags: [wiki, research, linear, workflow]
related: [2026-09-01-mnt-177-research-loop.md, 2026-09-10-mnt-200-update-research-loop.md, 2026-09-11-mnt-203-create-related-ticket-for-research.md]
---
# MNT-232: Update research flow

## TL;DR

Research now links the ticket it creates back to the originating ticket as
`related`, and instead of parking the source ticket in **Awaiting Input** it
moves it to **In Review** and marks the session step `researched`. The new
`related` relation is retried on transient Linear failures, so a flaky API call
no longer silently drops the link. Idempotency comes from the existing
title-based lookup in `create_research_ticket`, so no new column or migration
was needed.

---

## Overview

The research loop was built incrementally across three tickets:

- [[2026-09-01-mnt-177-research-loop]] — introduced the read-only
  `research-agent`, extracted the `## Research Report` section and **posted it
  as a Linear comment** on the source ticket, then moved the ticket to
  **Awaiting Input**.
- [[2026-09-10-mnt-200-update-research-loop]] — persisted the report to a new
  `sessions.research_report` column and added the `researched` `StepType`
  (navy badge in the frontend), but no workflow wrote that step yet.
- [[2026-09-11-mnt-203-create-related-ticket-for-research]] — replaced the
  comment with a dedicated research ticket created in the source project.
  `_find_existing_research_ticket` made creation idempotent by title.

MNT-232 closes the remaining gap: the created ticket was **not** related to the
original one, and the original ticket landed in Awaiting Input, which is a
dead-end state for a read-only research run.

### What was dropped

The branch as first written added a `sessions.research_ticket_id` column plus a
migration to hold the created ticket id for idempotence. That is redundant —
`create_research_ticket` already reconciles by deterministic title before
writing, which is a stronger guarantee than a local cache (it also survives
losing the DB row). The migration was additionally invalid: it reused revision
id `a3b4c5d6e7f8`, which master had already spent on
`add_sessions_research_report_column`, so any database that applied the earlier
revision would skip the new column entirely.

The branch also made `create_linear_ticket` omit empty *Tech Requirements* /
*Acceptance Criteria* sections. That existed only because the old research flow
called `create_linear_ticket` with empty strings; since MNT-203 the research flow
uses `create_research_ticket`, so the change was dropped as unrelated.

## Step 1 — Add the `IssueRelationCreate` mutation

New query at `demetra/queries/create_issue_relation.gql`, shaped like
`update_issue_status.gql`:

```graphql
mutation IssueRelationCreate($input: IssueRelationCreateInput!) {
  issueRelationCreate(input: $input) {
    success
    issueRelation {
      id
      type
      issue { id identifier }
      relatedIssue { id identifier }
    }
  }
}
```

## Step 2 — Add the `create_issue_relation` helper

**File:** `demetra/services/linear/mutations.py`

Follows the existing `update_ticket_status` shape — load the query, run the
request, return the `success` flag, and treat an empty or data-less response as
failure rather than raising:

```python
async def create_issue_relation(task_id: str, related_task_id: str, relation_type: str = "related") -> bool:
    query = await service.get_query(name="create_issue_relation")
    result = await service.graphql_request(
        query=query,
        variables={
            "input": {
                "issueId": task_id,
                "relatedIssueId": related_task_id,
                "type": relation_type,
            }
        },
    )
    if result is None:
        return False
    data = result.get("data")
    if data is None:
        return False
    return (data.get("issueRelationCreate") or {}).get("success", False)
```

Re-exported from `demetra/services/linear/__init__.py` with the other mutations.

## Step 3 — Link the research ticket

**File:** `demetra/workflows/research.py`

New `_link_research_ticket` helper, mirroring the retry shape of
`_create_research_ticket` with its own budget so a flaky Linear link cannot
starve the agent's retries. It raises after exhausting the budget: unlike the
status move, the link *is* part of the deliverable.

```python
async def _link_research_ticket(context: Context, research_ticket_id: str) -> None:
    attempts = MAX_ATTEMPTS["research"]
    while attempts > 0:
        try:
            linked = await create_issue_relation(
                task_id=context.linear_task.id, related_task_id=research_ticket_id
            )
        except LinearError as e:
            print_message(f"Failed to link research ticket: {e}, retrying.", style="warning")
            attempts -= 1
            continue

        if linked:
            return
        print_message("Linking the research ticket returned no success, retrying.", style="warning")
        attempts -= 1
    raise LinearError("Failed to link research ticket to the originating ticket after all attempts")
```

Re-running the step after a lost response is safe: Linear de-duplicates the
`related` relation, so a retry re-creates the same edge rather than a second one.

## Step 4 — Move to In Review and mark the step `researched`

`_move_to_awaiting_input` became `_move_to_in_review`. It still **tolerates**
failure — the research ticket already exists at that point, so a failed status
update is reported rather than discarding the deliverable:

```python
    await update_session_step(task_id=context.linear_task.id, step="researched", session_id=context.session_id)
    print_message("Task moved to In Review state.", style="result")
```

`_validate_research_ticket_prerequisites` was updated to check `in_review`
instead of `awaiting_input`, so a workspace without the In Review state fails
fast *before* the agent burns LLM calls on a retry that cannot succeed.

`researched` was already a valid `StepType` with frontend styling
(`.session-step.researched` in `react/src/App.css`) from MNT-200 — it simply had
no writer until now.

### Final step shape

```python
    created_ticket = await _create_research_ticket(context=context, report=report)
    if created_ticket is None:
        raise LinearError("Failed to create research ticket after all attempts")
    print_message(f"Created research ticket {created_ticket['identifier']}.", style="result")

    await _link_research_ticket(context=context, research_ticket_id=created_ticket["ticket_id"])

    await _move_to_in_review(context=context)
    return report
```

## Test Results

`uv run pytest tests/` — **946 passed**. `uv run ruff check .`, `ruff format`
and `uv run ty check` all clean.

New coverage:

- `tests/test_linear.py::TestCreateIssueRelation` — success, custom relation
  type, `success: false`, empty response, missing `data`.
- `test_run_research_step_creates_related_ticket_and_moves_to_in_review` — the
  full create → link → move path, asserting the relation arguments and the
  `researched` step.
- `test_run_research_step_retries_after_link_failure` — a transient link error
  retries without re-running the research agent.
- `test_run_research_step_raises_when_linking_fails` — exhausts the budget,
  raises, and never moves the ticket.

Existing research tests were updated for the new terminal state
(`test_run_research_step_fails_fast_without_in_review` replaces the
`..._without_awaiting_input` case).

---

## Follow-ups

- `main.py` sets `should_update_linear_status = False` for research contexts, so
  `linear_cleanup` no longer moves these tickets to In Review on exit. If the
  research step returns early (no report produced), the ticket stays wherever it
  was rather than being returned to TODO.
- The research ticket itself still lands in `prd` (MNT-203 behaviour). Worth
  confirming that matches the intended triage path now that the source ticket
  ends in In Review.

## References

- Related: [[2026-09-01-mnt-177-research-loop]]
- Related: [[2026-09-10-mnt-200-update-research-loop]]
- Related: [[2026-09-11-mnt-203-create-related-ticket-for-research]]
- External: https://linear.app/mnt/issue/MNT-232/update-research-flow