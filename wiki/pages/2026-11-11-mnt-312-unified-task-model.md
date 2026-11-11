---
title: Unified Task model with Linear and Chat subtypes
date: '2026-11-11'
type: implementation
status: resolved
session_id: ses_e3564c1b5ffeBDYG4coFDCd3Wo
services: [persistence, linear, chat, workflows, api, react]
branch: opencode/feature/MNT-312-unified-task-model
tickets: [MNT-312, MNT-311]
tags: [data-model, task, message, linear, chat, migration, backfill]
related: [2026-11-04-chat-session-list-and-rerun.md, 2026-11-03-ch-2-single-unified-session-view.md]
---

# Unified Task model with Linear and Chat subtypes

## TL;DR
Linear tickets and chat sessions are now driven by one generic `Task` entity with one generic
`Message` history, persisted in two new tables (`tasks`, `messages`) that sit beside the workflow
state in `sessions`. `LinearTask` + `LinearComment` and `Chat` + `ChatMessage` became subtypes of
those bases, `chats` shrank to a subtype row (`chats.id` + `chats.task_id`), the duplicate
foreign-key-less `chat_messages.session_task_id` column is gone, and a new `--linear-sync` CLI
backfills every issue of the linked Linear projects — with its comments — into the local store.
The `kind` discriminator (`linear` / `chat`) replaced the "does a `chats` row exist?" inference that
every list query used to need.

---

## Overview

Before this change the storage model had three shapes for two concepts:

- **Task identity** — lived in `sessions.task_id` (a Linear issue uuid **or** `CH-<id>`); the kind
  was never declared, it was inferred from the presence of a `chats` row.
- **Chat specifics** — lived in `chats` (a 1:1 subtype of `sessions`), where `title`,
  `description`, `tags`, `user_id` and `project_id` duplicated generic task fields.
- **Conversation** — lived in `chat_messages` for chats only, while Linear comments were fetched
  live; two paths to one history, with `chat_messages.session_task_id` carrying no FK while
  `chat_messages.chat_id` did.

The pipeline was written against `LinearTask`, so chat mode *fabricated* one
(`build_chat_task` in `demetra/services/chat/tasks.py`) rather than branching every workflow. The
research ticket MNT-312 confirmed the direction was inverted: the generic type has to be the base,
with `LinearTask`/`Chat` as two implementations behind one interface.

## Step 1 — The model layer

**File:** `demetra/library/models.py:39`

`Task` and `Message` are keyword-only dataclasses (`kw_only=True`) so subtypes can add defaulted
fields without the "non-default argument follows default argument" error plain dataclass
inheritance raises:

```python
@dataclass(kw_only=True)
class Task:
    id: str
    kind: TaskKind          # "linear" | "chat"
    identifier: str
    title: str
    description: str = ""
    priority: int = 0
    state: str | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    project_id: str | None = None
    project_name: str | None = None
    user_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    messages: list["Message"] = field(default_factory=list)
```

Subtypes:

- `LinearTask(Task)` — `kind="linear"` plus `linear_issue_id`, `linear_identifier`,
  `linear_state_id`, `linear_state_name`, `linear_project_id`, `branch_name`.
- `Chat(Task)` — `kind="chat"` plus `chat_id` (the `chats` serial).
- `Message` — `id`, `task_id`, `body`, `created_at`, `parent_id`, `source`, `external_id`,
  `author_id`, `author_name`, `is_system`, `kind`.
- `ChatMessage(Message)` (`source="chat"`) and `LinearComment(Message)` (`source="linear"`,
  `kind="comment"`).

Two field merges came out of this:

- **`labels` → `tags`.** Linear label names and chat tags are the same concept ("functional
  labels on a work item"), so they are one column now.
- **`comments: list[str]` → `messages: list[Message]`.** `Task.text` (the prompt body) renders
  `Task.message_bodies`, so the LLM input is unchanged.

`Context.linear_task` became `Context.task` (144 references across 20 files, renamed mechanically).
`Context.is_chat` now reads `self.chat is not None or self.task.kind == "chat"`.

## Step 2 — The schema

**File:** `demetra/library/tables.py:22`, `migrations/versions/a9b0c1d2e3f4_add_tasks_and_messages_tables.py`

```
tasks        id PK (Linear issue uuid | "CH-<id>"), kind, identifier, title, description,
             priority, state, url, tags JSONB, project_id FK→projects (SET NULL), user_id,
             created_at, updated_at
linear_tasks task_id PK/FK→tasks, linear_issue_id UNIQUE, linear_identifier, linear_state_id,
             linear_state_name, linear_project_id, branch_name
messages     id PK, task_id FK→tasks, parent_id FK→messages, source, external_id, author_id,
             author_name, is_system, kind, body, created_at
             + partial unique index on external_id WHERE external_id IS NOT NULL
```

`sessions.task_id` became a foreign key to `tasks.id`, and `chats` shrank to `id` + `task_id`.

**Why `tasks.id` reuses the old `sessions.task_id` values** (the Linear issue uuid, `CH-<id>`):
the session rows then need no rewrite, the FK is a pure addition, and the API task ids stay
stable. `chats.id` is kept as a serial because the `CH-<id>` task id is derived from it.

**`tasks.project_id` has a FK but `tasks.user_id` does not.** The project id must be validated —
`create_chat` relies on it to reject a chat for a non-existent project — but `sessions.user_id` has
never been a FK (`DEFAULT_USER_ID` and test fixtures use ids that are not in `users`), so adding
one would break existing write paths. `ensure_task` resolves the project through a subquery, so an
unknown project id is stored as NULL instead of raising.

### The data migration

The revision is one transaction and carries the data with it:

1. create `tasks`, `linear_tasks`, `messages`;
2. back-fill `tasks` from `chats` (kind `chat`) and from the remaining `sessions` (kind `linear`);
3. copy `chat_messages` into `messages` (source `chat`), then drop `chat_messages`;
4. re-point `chats.session_task_id` → `chats.task_id` and drop the duplicated generic columns;
5. add the `sessions.task_id` → `tasks.id` foreign key.

The linear back-fill has to split the session display name back into an identifier and a title,
because `sessions.name` is the only local record of a Linear ticket:

```sql
CASE WHEN position(':' in s.name) > 0 THEN split_part(s.name, ':', 1) ELSE s.name END   -- identifier
CASE WHEN position(':' in s.name) > 0 THEN trim(substr(s.name, position(':' in s.name) + 1)) ELSE s.name END
```

Dangling `project_id` / `user_id` values are dropped with an `EXISTS` guard, because `sessions`
never enforced them. `downgrade()` restores the previous tables and re-populates them from
`tasks` / `messages`; the round trip is exercised by
`tests/test_task_message_migration.py`, which runs the revision against a throwaway schema.

## Step 3 — The service layer

**File:** `demetra/services/linear/mirror.py` (new)

`LinearTask` was a dataclass hydrated from the Linear API on every run — there was no local
Linear store at all. The mirror adds one:

- `store_linear_issue()` writes the issue into `tasks` + `linear_tasks` and its comments into
  `messages`, keyed by the Linear comment id (`external_id`) so a re-run is idempotent.
- Threaded replies resolve their `parent_id` to the *local* message id, not the Linear comment id —
  the first version stored the Linear id and violated `messages_parent_id_fkey`.
- `get_linear_task_by_id()` still fetches live from Linear (the API stays the source of truth for
  the pipeline) and mirrors the result on the way through.

**File:** `demetra/services/linear/sync.py` (new)

`sync_linear_mirror()` walks the Linear projects linked to Demetra projects (`projects.linear_project_id`)
and mirrors every issue with its comments. The existing `.gql` documents use `first: 100` with no
cursor, so two new documents were added with proper Relay pagination:

```
demetra/queries/get_project_issues.gql   issues(first: 50, after: $after) { pageInfo { hasNextPage endCursor } nodes { ... } }
demetra/queries/get_issue_comments.gql   issue(id: $issueId) { comments(first: 50, after: $after) { pageInfo { ... } nodes { ... } } }
```

The CLI entry point mirrors the `--allowlist seed-existing` shape:

```bash
uv run python main.py --linear-sync --dry-run   # count only
uv run python main.py --linear-sync             # write
```

**File:** `demetra/workflows/notifications.py`

`notify_message` is still the single fork, but both branches now record the message locally:

```python
comment_id = await post_comment(task_id=context.task.id, body=body)
if not comment_id:
    return False
await record_linear_comment(task_id=context.task.id, body=body, kind=kind, external_id=comment_id)
```

`post_comment` therefore returns the created comment id (`str | None`) instead of a bool — the id
is what makes the local row idempotent against the backfill.

## Step 4 — API and frontend

`GET /api/v1/sessions` now returns `kind` (`linear` / `chat`) and `task_title` next to the
existing `chat_id`. The frontend badge stopped inferring the kind from `chat_id`:

```tsx
const isChat = session.kind === "chat";
```

`Chat.id` is now the task id (`"CH-12"`, a string) and `Chat.chat_id` carries the serial; the
`session_task_id` field is gone from the payload and the TS interfaces.

## Test Results

```
uv run pytest tests/ -q          1291 passed
uv run ruff check .               All checks passed!
uv run ty check                   All checks passed!
uv run pre-commit run --all-files all hooks passed
cd react && npx tsc --noEmit      clean
cd react && npx vitest run        168 passed
```

The migration was verified against a scratch Postgres database: `upgrade head` → `downgrade -1` →
`upgrade head` with seeded chat and Linear rows, and separately by
`tests/test_task_message_migration.py`.

---

## Follow-ups

- The Linear mirror is **backfill-only** (the decision taken for this ticket): the local copy goes
  stale until the next `--linear-sync`. A Linear webhook receiver for `Issue`/`Comment` events
  would keep it fresh — that was the other option considered and it was explicitly deferred.
- `Task.state` is `NULL` for chats: the chat's state is `sessions.step`, and duplicating it would
  create a second source of truth. Linear tasks carry their Linear state name.
- `tasks.project_id` is `SET NULL` on project deletion, so a deleted Demetra project leaves its
  Linear mirror rows without an owner. `delete_project` refuses to delete a project that still
  owns chat tasks.

## References

- Related: [[2026-11-04-chat-session-list-and-rerun]], [[2026-11-03-ch-2-single-unified-session-view]]
- External: MNT-312 (research), MNT-311 (original ticket)
