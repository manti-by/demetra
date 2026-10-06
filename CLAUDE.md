# CLAUDE.md

@AGENTS.md

The file above is the source of truth for project structure, layering, code conventions and commands. This file adds only Claude Code specific guidance. Do not duplicate AGENTS.md content here; fix it there.

## Before You Start

- Skim `wiki/INDEX.md` (`## By topic`) for prior sessions on the subsystem you are touching, then read the relevant `wiki/pages/*.md`.
- The wiki MCP tools (`wiki_search`, `wiki_get_page`, `wiki_list_pages`) are served by `demetra/mcp_server.py` and are not configured for Claude Code (no `.mcp.json`). Use Grep/Read on `wiki/pages/` instead, e.g. grep frontmatter `tickets:`, `services:`, `tags:`.
- Pages in `wiki/archive/` are retired. Use them only for provenance, not as current behaviour.
- When a wiki page and the code disagree, the code wins. Record unresolved conflicts in `wiki/QUESTIONS.md` under `## Open`.

## Git Conventions (Observed)

The repo history does not follow the branch and commit format described in AGENTS.md. Match the history:

- Branches: `mnt-<id>-<kebab-description>` (e.g. `mnt-225-add-copy-button`).
- Commits: `MNT-<id>: <Imperative summary>` (e.g. `MNT-225: Add copy button`, `MNT-225: Fix review findings`). If there is no ticket, use a plain imperative summary.
- Never commit to `master` and never push without being asked.

## Verification

Run these before you call a change done:

```bash
uv run ruff check . && uv run ty check    # lint + types
uv run pre-commit run --all-files         # full hook set (CI runs this)
uv run pytest tests/<file>.py -q          # targeted tests first, then `make test`
make check-migrations                     # after touching migrations/ or DB models
cd react && bun run test && bun run build # after touching react/
```

- `make check` runs `git add .` first, which stages every file in the working tree. Do not use it. Run its steps directly.
- Tests need a local Postgres. `tests/conftest.py` drops and recreates a `test_demetra` database and points `DATABASE["name"]` at it, so tests never touch the real `demetra` DB. Do not bypass this fixture.
- Prefer real fixtures and factories over `patch`. Mock only third-party calls such as Linear, GitHub, OpenRouter and OpenCode (see `wiki/pages/2026-06-15-remove-patches-from-tests.md`).

## Recurring Pitfalls (from the wiki)

- Rich markup: route all console output through `print_message` (`demetra/services/runtime/tui.py`), which escapes input. Raw agent or review text passed to Rich crashes the workflow on `[/...]` (`2026-07-21-rich-markuperror-and-run-attempts`).
- Worktrees: workflows run inside per-session worktrees, not the main checkout. Build paths from the context/worktree, never from `BASE_PATH` (`2026-06-03-context-bloating`, `2026-08-25-mnt-187-wiki-pages-not-generated`).
- Environment: read workflow config via `Context.environment` (`SessionEnvironment`). Do not read `settings.py` or `os.environ` directly in workflows (`2026-09-16-mnt-205-revise-merged-environment`). Only allowlisted OS env vars reach agent subprocesses (`OS_ENV_ALLOWLIST` in `demetra/library/constants.py`).
- Session state: `sessions.step` drives resume logic. Any new terminal or awaiting state must be checked durably on re-entry, not only in the current run (`2026-08-28-awaiting-input-workflow-continues-to-review`, `2026-07-16-fix-empty-build-plan-loop`).
- Subprocess limits: long agent and clone calls need `SUBPROCESS_TIMEOUT` (`demetra/settings.py`), not a short shell timeout (`2026-06-10-fix-project-creation-timeouts`). Watch for silent truncation of arguments and output (`2026-08-04-fix-resolve-agent-truncated-context`, `2026-09-14-listener-readline-limit-crash`).
- Version bumps: `bump_project_version` defaults to patch. Major bumps are manual-only.

## Off-Limits

- Do not read or edit `.env`, `.env.docker`, `.keys/` or other secret files. Use `.env.docker.example` for reference.
- Do not run `make deploy`, `docker-clean`, `gh-use-*` or anything that sshes into production hosts unless explicitly asked.

## After a Session

For non-trivial work, add a wiki page from `wiki/TEMPLATE.md` at `wiki/pages/YYYY-MM-DD-<topic>.md`. Fill in the frontmatter, cross-link with `[[...]]` mirrored in `related:`, and add a line to the top of `## Pages` in `wiki/INDEX.md` (newest first). Leave the `## By topic` clusters to the `wiki-consistency` skill.
