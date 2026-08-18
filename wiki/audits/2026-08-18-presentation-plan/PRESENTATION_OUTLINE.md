# Demetra Presentation Outline

A 24-slide deck about the Demetra autonomous coding supervisor — one slide per
section, in the order they make sense to present. Use this as a script outline
during talk prep; trim or reorder as needed.

---

## Slide 1 — Title

**Demetra** — autonomous coding supervisor that coordinates AI agents across
Linear / OpenCode / Cursor / CodeRabbit to take a ticket from `TODO` → merged
PR.

## Slide 2 — The big picture

End-to-end loop: `Linear TODO` → **R&D (plan)** → **build + review** → **PR** →
`Linear Done`. Entry point: `main.py:66` `async def main()`. Always updates
Linear status in the `finally:` block (`main.py:149`).

## Slide 3 — Daemons

Two long-running processes feed work in:

- `demetra/watcher.py` — polls Linear `TODO` column
- `demetra/listener.py` (driven by `demetra/services/daemons/listener.py`) —
  reacts to GitHub PR notifications (review / checks / rebase triggers)

## Slide 4 — R&D: Linear → Plan agent wiring

`demetra/workflows/plan.py:run_plan_step` runs `opencode_plan_agent` (headless
OpenCode CLI subprocess in `demetra/services/agents/opencode.py`), then
`extract_plan` (OpenRouter) → `extract_questions`. Output posted back to Linear
as a comment.

## Slide 5 — Question extraction & Auto mode

Three operating modes (`main.py:39-47`):

- `--auto` (default) — extract questions, post to Linear, exit
- `--plan-loop` — answer questions automatically by looping `plan ↔ resolve`
- interactive — `user_input()` prompt via `demetra/services/runtime/flow.py`

`extract_questions` in `demetra/services/llm/openrouter.py`.

## Slide 6 — Git worktrees & branching

`demetra/workflows/setup.py:setup_workflow` creates a **dedicated git worktree**
per ticket, branch named `<agent>/feature/<issue-id>-<slug>` (e.g.
`opencode/feature/DEMETRA-10-add-user-authentication`). Isolates concurrent runs
and makes cleanup trivial.

## Slide 7 — Build loop

`demetra/workflows/build.py:run_build_step` runs `opencode_build_agent` inside
the worktree. Retries up to `MAX_BUILD_ATTEMPTS` (`demetra/settings.py`); if
no staged changes, the plan is re-injected with *"you MUST implement and stage"*.
`commit_and_push` finalises the commit.

## Slide 8 — Context tracking & session history

Every OpenCode agent run persists a row to `session_history` (table at
`demetra/library/tables.py:130`) carrying `SessionHistory` + `TokenUsage`
(input, output, reasoning, cache read/write, **context tokens**) — model
defined in `demetra/library/models.py:65`, recorded via `record_session_history`
(`demetra/services/persistence/database.py:720`). Surfaced to the UI through
`GET /sessions/{task_id}/history` (`demetra/api/sessions.py:53`) → the
*Session History* modal in React. See
`[[2026-07-23-session-history-modal]]` and the rev validation audit
`[[2026-07-23-session-tokens-audit-revalidation]]`.

## Slide 9 — Context compaction

`CONTEXT_COMPACTION_THRESHOLD` env (`demetra/settings.py:51`, default 100k).
`check_and_compact_context` (`demetra/workflows/build.py:49`) inspects each
agent run's `context_tokens` field; when over the threshold it invokes `/compact`
via `opencode_compact_session`. The compaction event itself lands in
`session_history` so the operator can see when it fired and what the model was.
Implementation tracked in `[[2026-07-07-add-context-compaction]]` (disabled by
MNT-145, re-enabled in `47d428d`).

## Slide 10 — Validate agent

`demetra/workflows/validate.py` — *read-only* OpenCode agent cross-checks the
staged diff against the build plan, returns *"missing items"* (`Plan step N: …`).
Findings feed back into build if any plan item is uncovered before review even
starts. Implementation: `[[2026-08-05-post-build-validation]]`.

## Slide 11 — Lint & test (opt-in)

`demetra/workflows/lint.py` + `demetra/services/quality/{lint,test}.py`. Gated
by the `FEATURES` dict in `demetra/settings.py` (`IS_RUFF_ENABLED`,
`IS_PYTEST_ENABLED`, both default `False`) — only runs when the package is
installed *and* the matching flag is on. Toggled via env, code-side zero cost
otherwise.

## Slide 12 — Review loop

`demetra/workflows/review.py:run_review_agents` runs the configured reviewers
**in parallel** (OpenCode review, Cursor, CodeRabbit — implementations in
`demetra/services/agents/`). Retries up to `MAX_REVIEW_ATTEMPTS`, findings
re-injected into build.

## Slide 13 — Review summarization

`summarize_review` in `demetra/services/llm/openrouter.py` collapses noisy
multi-agent findings into one actionable summary. Same OpenRouter module also
serves plan extraction and PR-description generation; migrated from Groq in
`[[2026-08-18-migrate-llm-groq-to-openrouter]]`.

## Slide 14 — PR lifecycle & merge

After a clean build: PR opened via `demetra/services/vcs/github.py`. Listener
picks up `CHANGES_REQUESTED` → re-enters the review loop, or merged via
`demetra/workflows/merge.py`. `cleanup_workflow` removes the worktree.

## Slide 15 — Failure handling

`demetra/workflows/failure.py:process_pr_failure` for `PullRequestError`;
`AutoCancelledError` keeps Linear in `awaiting_input`; `InfiniteLoopError`
exits. A wiki page is still written on partial success.
See `[[2026-07-16-fix-notification-mark-read]]` for the
`MAX_LISTENER_ATTEMPTS` infinite-loop guard.

## Slide 16 — Wiki: the persistent memory

`wiki/` — one Markdown page per session. `main.py:153` calls
`write_session_wiki_page` after every successful session, so the knowledge base
compounds automatically. Frontmatter (`title / date / type / services /
tickets`), `[[wikilinks]]`, served to agents and humans via MCP tools.

## Slide 17 — Wiki conventions & cross-linking

Four page types in `wiki/TEMPLATE.md`: `debug`, `investigation`, `code-review`,
`implementation`. Naming: `pages/YYYY-MM-DD-kebab-topic.md`. Index lives in
`wiki/INDEX.md`, open questions in `wiki/QUESTIONS.md`. Editors must keep
`related:` frontmatter in sync with body `[[links]]` — that's what turns a
folder of notes into a queryable knowledge graph. Agents must `wiki_search`
before planning any subsystem touched before.

## Slide 18 — Wiki maintenance services

`demetra/services/wiki/` subpackage — `facts.py` (extraction), `parsing.py`,
`naming.py`, `index.py` (keeps `INDEX.md` current), `render.py`,
`maintenance.py`. Refactor history: `[[2026-08-07-split-wiki-service-into-subpackage]]`.
Edge cases hardened in `[[2026-08-09-wiki-fixes-and-test-optimization]]`.

## Slide 19 — External surface: API + MCP + Frontend

Three entry points into the same domain layer:

- **REST** — `demetra/app.py` + `demetra/api/*` FastAPI dashboard
- **MCP** — `demetra/mcp_server.py` over stdio (covers slides 20)
- **React UI** — `react/` Vite + TypeScript supervisor dashboard

## Slide 20 — MCP server & tools

`demetra/mcp_server.py` is a stdio MCP server using mcp 2.0
`on_list_tools` / `on_call_tool` callbacks (migration:
`[[2026-08-03-fix-mcp-server-2.0-api]]`). `demetra/tools/__init__.py`
aggregates tool modules; each exposes `async def list_tools()` and
`async def call_tool(name, arguments)`, returning a shared `ToolResult(content, is_error)`.

Tool families currently shipped:

- **wiki** — `wiki_search` / `wiki_get_page` / `wiki_list_pages`
  (`[[2026-08-03-wiki-mcp-tools]]`)
- **Linear** — full GraphQL surface (`Linear_get_issue`, `Linear_save_issue`,
  `Linear_list_issues`, diffs, comments, projects, releases, cycles…)
- **DB inspection** — `list_tables`, `query_table`, `get_table_definition`,
  `get_table_count`
- **logs** — `list_log_files`, `tail_logs` over `/var/log/demetra`
- **browser** — Playwright-driven UI automation (`browser_navigate`,
  `browser_click`, `browser_snapshot`, etc.)

Allowlist-gated auth for the Linear tools is in
`demetra/services/auth/allowlist.py`. These tools are what let OpenCode query
the wiki before planning and what give operators a typed interface into the
running platform.

## Slide 21 — Strict architecture layering

(from `AGENTS.md`) one-way dependencies only:

```
library/  → pure data: dataclasses, TypedDicts, exceptions
  ↓
services/<system>/  → external integrations (linear, github, wiki, llm, …)
  ↓
workflows/<step>.py  → orchestrators (setup, plan, build, validate, review, merge, …)
  ↓
api/  → FastAPI routers (thin, delegate to services)
tools/  → MCP tool modules (dispatch to services / persistence)
  ↓
mcp_server.py / app.py (composition root)
```

The wiki, services persistence, and LLM modules are all behind this layering —
no skipping.

## Slide 22 — Persistence

`demetra/services/persistence/` — SQLAlchemy DB (sessions, tickets,
`session_history`), RQ queue (`queue.py`), Fernet encryption for tokens at rest
(`encryption.py`). Schema migrations under `migrations/`, driven by
`alembic.ini`. Session-row write used by the cleanup workflow:
`mark_session_posted`.

## Slide 23 — Containerized deploy

`make docker-deploy` brings up Postgres + Redis + api / worker ×4 / watcher /
listener / rq-dashboard + a one-shot React build (see
`[[2026-08-10-docker-compose-deploy]]` and the shared-anchor refactor
`[[2026-08-18-compose-anchors-refactor]]`). Systemd units and nginx config live
under `configs/`.

## Slide 24 — Closing: why it works

The compounding loop: tickets drive sessions → sessions write wiki pages → wiki
pages make future planning better → faster merges feed the same loop.
Guardrails that keep it sane: git-flow rules in `AGENTS.md`, per-ticket
worktree isolation, opt-in lint/test, structured exception handling, and
**persistent context**: `session_history` for audits + `CONTEXT_COMPACTION_THRESHOLD`
for long-agent runs. Plus the MCP tool surface that lets the agents read what
earlier agents learned.

---

## References

- Related wiki: [[2026-07-23-session-tokens-audit-revalidation]] (session
  history & compaction data validation), [[2026-08-03-wiki-mcp-tools]],
  [[2026-08-05-post-build-validation]], [[2026-07-23-session-history-modal]]
- External: `AGENTS.md` (project conventions), `wiki/README.md` (wiki schema)
