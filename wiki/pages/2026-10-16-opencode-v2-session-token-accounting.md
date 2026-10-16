---
title: OpenCode v2 migration — CLI ground truth, the compaction no-op, and the corrected MNT-251 plan
date: 2026-10-16
type: investigation
status: reference
session_id: ses_ebbe29029ffeah3TJhfQdO7HzB
services: [agents, persistence, workflows, api]
branch: -
tickets: [MNT-251, MNT-246, MNT-241, MNT-245, MNT-234]
tags: [opencode, cli-v2, tokens, sessions, accounting, compaction, session-history]
related: [2026-07-16-session-history-tokens-null.md, 2026-08-19-build-agent-stale-session-deleted-worktree.md, 2026-07-23-session-tokens-audit-revalidation.md, 2026-09-30-mnt-228-intermediate-history-states.md, 2026-08-25-mnt-181-total-tokens-counter.md, 2026-07-23-session-history-modal.md, 2026-07-07-add-context-compaction.md, 2026-10-06-unify-subprocess-env-on-session-environment.md]
---

# OpenCode v2 migration — CLI ground truth, the compaction no-op, and the corrected MNT-251 plan

## TL;DR

**Correction (2026-10-16 14:14):** the first version of this page said production token accounting was "silently dead". That was **wrong** — see `## Update — 2026-10-16 14:14` below. Production runs opencode **1.18.30**, where `export`, `db`, `agent list` and `run --dir` all still work, so MNT-246's measurements (including the 6.4× inflation) describe live production accurately. Everything v2-specific below is a **forward-looking** landmine, not current breakage.

The MNT-241 epic's evidence base was gathered on opencode **1.18.35**, which matches production. But `Dockerfile:14` installs from a floating URL that resolves to **2.0.30 — published today** — so the next `make docker-build` upgrades the CLI and breaks **every agent invocation at once**, because v2's `run` removed the `--dir` flag that `opencode.py:342` passes on all nine agent paths. Re-probed on v2.0.30: three of MNT-246's load-bearing findings are falsified (NEW-3, NEW-8-as-stated, NEW-7), and one measurement **reverses a design instruction** in MNT-246 §d — a fork's `info.tokens` *restarts* rather than inheriting, so seeding a fork's cursor from its parent would record build's entire spend as **zero**. Separately, context compaction was found to be a **no-op that has never worked on either version**. MNT-251 was rewritten as the two-phase implementation target with these measurements recorded; MNT-246 was annotated and closed as research-complete.

---

## Net effect

Two distinct problems, with different timelines:

**Live today, on opencode 1.18.30 (production):** context compaction is a **no-op that has never worked**. `opencode_compact_session` passes `/compact` as the *message positional*, which both 1.18.30 and v2 deliver to the agent as a prompt rather than executing as a command. So every time a build session crosses `CONTEXT_COMPACTION_THRESHOLD` (100,000), Demetra pays for a full-context LLM turn that returns a role-played acknowledgment, and the session keeps growing. Separately, MNT-246's token inflation (6.4× overall, 19.1× on the retained window) is the **current** production state, not a stale measurement.

**Latent, detonating at the next `make docker-build`:** v2.0.30 removed `run --dir`, which `opencode.py:342` passes on every plan, build, validate, review, resolve, research, merge, rebase and review_fixes invocation. It also removed `export`, `db`, `agent`, and `run --command`, and changed the `messages[]` shape. The image installs from a floating URL, so a rebuild upgrades the CLI with no signal and every agent run starts exiting 1.

The over-report the epic was created to fix therefore has to be solved *together* with the v2 migration — repairing the export path without the delta model just restores the inflation, and migrating without the delta model bakes it in.

The durable value of this page is the **v2 CLI ground truth** in the next two sections. It exists nowhere else in the repo, and every future ticket touching opencode token or session handling needs it.

---

## Why it will break — the unpinned CLI

**File:** `Dockerfile:14`

```dockerfile
RUN curl -fsSL https://opencode.ai/v2/install | bash
```

`.env.docker.example:14` sets `OPENCODE_PATH=/usr/local/bin/opencode`, and `Dockerfile:37` copies the builder's `/root/.opencode/bin/opencode` to that path. The install script resolves the version at build time from `https://opencode.ai/update/api/latest/cli/npm`.

**Established by measurement, not inference:**

- `~/.opencode/bin/opencode` — the `OPENCODE_PATH` default, and the binary the image bakes — reports **1.18.30**, and its `run --help` documents `--dir`, `--command`, `--fork`, `--session`, `--format`, `--title`, `--agent`. This matches MNT-246's "opencode 1.18.35" and confirms production is on the 1.x line today.
- `https://opencode.ai/update/api/latest/cli/npm` returns `{"channel":"latest","version":"2.0.30", ...}` with a `time_created` of **today**. So v2.0.30 is what the next image build installs.
- The `opencode` first on this machine's `PATH` is `~/.bun/bin/opencode` (npm `@opencode/cli`, symlinked today) → **v2.0.30**. All the v2 probes below used that binary; the 1.18.30 probes used the explicit `~/.opencode/bin/opencode` path under an isolated `HOME` so it could not touch the shared v2 session store.

Between 1.18.30 and 2.0.30 four flags/subcommands Demetra depends on vanished with no signal — `run --dir`, `run --command`, `export`, `db`, `agent` — and the agent-fallback semantics changed from silent-degrade to hard-fail.

**File:** `demetra/services/agents/opencode.py:342`

```python
command = [str(OPENCODE["path"]), "run", "--dir", str(target_path), "--model", model, "--agent", agent]
```

On v2 this exits 1 with `Unrecognized flag: --dir in command opencode run` — for **every** agent invocation, on all nine workflows. `run_command` (`services/runtime/subprocess.py:127-133`) already sets `cwd=target_path`, so the flag is redundant and dropping it is the minimal fix.

**File:** `demetra/services/agents/opencode.py:432`

```python
command = [str(OPENCODE["path"]), "export", session_id]
```

Works on 1.18.30 (this is why MNT-246 could read tokens at all). On v2 it exits 1 (`Unexpected positional argument: "<ses_id>"`) and `get_opencode_session_tokens` returns `None` at `opencode.py:436-437`. Pinning the image was **explicitly declined**, so it is recorded in MNT-251 §12 as an accepted risk — though the blast radius is now known to be total rather than gradual, and the ticket asks for that decision to be revisited. Mitigations that don't require pinning: log `opencode --version` at startup, make the export path fail loudly instead of returning `None`, and add a startup smoke test asserting the flags and subcommands Demetra passes.

---

## Phase 0 spike measurements (v2.0.30, 2026-10-16)

Three funded runs, ~$0.003 total, in a scratch dir with **no** local `.opencode/agents/` so the global-install path was exercised deliberately.

### The decisive fork measurement

- **Parent session** (one trivial turn) — `info.tokens = {input 7816, output 1, reasoning 0, cache.read 132, cache.write 0}`, `info.cost = 0.00235392`
- **Fork of that session** (one trivial turn) — `info.tokens = {input 37, output 1, reasoning 0, cache.read 7934, cache.write 0}`, `info.cost = 0.00048834`

**A fork's `info.tokens` restarts. It does not inherit the parent's cumulative.** MNT-246 open question #2 guessed the opposite. The inherited context re-enters as **`cache.read`** (7934 ≈ parent's 7816 + 132), not as `input`.

Two consequences, both load-bearing:

1. **Do not seed a fork's cursor from its parent.** MNT-246 §d.3's rule `cursor None => delta = new_cum` is *already correct* for forks. Seeding would compute `max(0, 37 - 7816) = 0` and record build's entire spend as **zero**. `fork_of` is lineage metadata only and must never feed the delta.
2. **Forked context is billed twice under cache-inclusive totals** — once as the parent's `input`, once as the fork's `cache.read`. That is honest accounting, and it is a direct argument for keeping the Total cache-inclusive: a billable-only metric would hide the cost of the fork-once design entirely.

Also verified: a fork **inherits the parent's agent** (fork messages begin with `agent-switched → validate-agent` without `--agent` being passed), and the fork's title mutates to `"<title> (fork #1)"` — so title-based session identification breaks the moment `--fork` is used.

### `--format json` event schema (NEW-1 confirmed, key name unchanged)

Events are `{type, timestamp, sessionID, part}`. The key is still **`sessionID`**, and it is present on `step_start`, `text` **and on `error` events** — so the session id is capturable even for a failed run. Assistant text is at `part.text` where `type == "text"`, making reassembly a simple ordered concat.

### Agent errors move between streams depending on format

- **default format** (what production runs today) — exit **1**, stdout empty, stderr `Error: Agent not found: "X"` (ANSI-wrapped; `live_stream` already applies `ansi_strip`, so captured stderr is clean)
- **json format** — exit **1**, **stderr empty**, stdout carries `{"type":"error","timestamp":...,"sessionID":"ses_...","error":{"type":"unknown","message":"Agent not found: \"X\""}}`

All nine workflows build messages as `stderr.strip() or stdout.strip() or 'unknown error'` (e.g. `build.py:96-99`, `plan.py:86-89`, `validate.py:47-50`). Post-migration that renders raw NDJSON to operators and into Linear failure comments. The wrapper must parse `type == "error"` events and surface `error.message`.

### Pipe truncation is subcommand-specific, not a uniform 64 KB cap

- `session list --format json -n 500` through a pipe — **140,107 bytes**, byte-identical to the file redirect, parses cleanly (500 sessions). NEW-8 **falsified as stated**.
- `session export <ses_id>` through a pipe — **393,216 bytes** vs **437,195** to a file, and 393,216 is exactly **6 × 65,536**. The piped bytes are **invalid JSON** (`JSONDecodeError` at char 441510). The defect class is very real.

So `run_command_to_file` stays mandatory for export, and `run --format json` must be treated as truncation-exposed until measured on a production-sized stream (the 605-byte probe says nothing about a real build).

### NEW-3 falsified: per-message sums do not equal `info.tokens`

On a 34-assistant-message session:

- `info.tokens` — `{input 810, output 33339, reasoning 0, cache.read 1933679, cache.write 300639}`
- `sum(messages[].tokens)` — `{input 204, output 33321, reasoning 0, cache.read 1933679, cache.write 300639}`

`input` under-counts ~4×; `cache.read`/`cache.write` match exactly. `sum(messages[].cost)` 1.435351 vs `info.cost` 1.435421 — same direction.

Two causes identified: on a **fork**, `messages[]` includes the copied parent turns while `info.tokens` restarts, so the two are inconsistent *by construction*; and v2 exposes internal agents (`compaction`, `summary`, `title`) that plausibly count toward session totals without appearing in `messages[]`. MNT-246 §d.3's `new_cum = sum over messages[]` must become `new_cum = info.tokens`.

### `opencode debug agents` is NOT a usable preflight probe

- From the demetra repo — **15** agents: the eight repo agents **with their `-agent` suffix** plus built-ins `build`, `plan`, `compaction`, `explore`, `general`, `summary`, `title`.
- From a directory with no local `.opencode/agents/` — **`[]`, zero agents**, even though `~/.config/opencode/agents/` held all eight `*-agent.md` files, `opencode debug config` confirmed the global `opencode.json` was loaded, and a run with `--agent validate-agent` from there recorded **`info.agent = "validate-agent"`** with exit 0.

`debug agents` is project-scoped and blind to the global install. The container relies on exactly that global install (`Dockerfile:51`), so a `debug agents`-based preflight would emit a false "missing agent" warning for **every project in production**. This killed MNT-251's original design (its step 1 expected "all eight" *bare* names; the real ids are `-agent` suffixed and there are 15, not 8).

### NEW-7 is obsolete on v2

A nonexistent agent no longer falls back to `build` — it exits **1**. Demetra's existing `if exit_code != 0: raise BuildError/PlanError` paths already fail loudly, for free. The 1.18.35 marker string `not found. Falling back to default agent` **does not exist on v2**; do not add it as a constant.

### `ceac6b9` confirmed correct on v2

The global install *does* make agents resolve from any `--dir`: `--agent validate-agent` resolved from a bare directory via `~/.config/opencode/agents/`, recording `info.agent = "validate-agent"`. MNT-251's "the shipping half is already fixed and must be verified, not rewritten" premise holds — the *detection* half was what became obsolete.

---

## v2 shape reference

### `info` (from `session export`)

Keys: `{agent, cost, id, location, model, outcome, projectID, time, title, tokens}`. **There is no `parentID` key at all** — NEW-2 holds, fork lineage must live in Demetra's DB.

- `info.tokens` — `{input, output, reasoning, cache: {read, write}}`, **unchanged from 1.18.35**, so `opencode.py:451-473` keeps working once the command is fixed
- `info.model` — **dict** `{id, providerID, variant}`, not a string; serialize as `f"{providerID}/{id}"` plus `#variant` when not `default`, matching the `--model` format `opencode run` expects
- `info.time` — `{created, updated, idle, viewed}`
- `info.outcome` — e.g. `"succeeded"`, a stronger success signal than the exit code alone
- `info.cost` — USD, session-level; cross-checks against `opencode stats`
- `info.agent` — the agent **actually** used; verified accurate

### `messages[]`

Entries are `{id, time, type, agent, model, content, snapshot, finish, rawFinish, cost, tokens}`. **There is no `info` wrapper** — this is the second, independent reason compaction is dead.

- Role is `msg["type"]`, observed values `user`, `assistant`, `idle`, **`agent-switched`** — not `msg["info"]["role"]`
- Per-message tokens are at `msg["tokens"]`, same field shape as `info.tokens`
- `msg["cost"]` is per-turn USD
- `msg["time"] = {created, streamed, completed}`; `time.created` is **monotonic across messages** (verified), so it remains a valid cursor watermark

**File:** `demetra/services/agents/opencode.py:475-506` reads `msg["info"]["role"]` and `msg["info"]["tokens"]`, so its `isinstance(msg_info, dict)` guard fails for **every** message and `latest` stays `None` — `usage.context` is never set even after the export command is fixed.

### Subcommands removed in v2 (all exit 1)

- `opencode export <id>` → **`opencode session export <id>`** (no `--format` flag; adds `--sanitize`, which must NOT be passed — Demetra needs the real transcript)
- `opencode db "<sql>"` → **gone, no replacement.** Every `opencode db` verification command in MNT-246 §f is unexecutable, and §d.3's recommended incremental read (`SELECT ... WHERE message.id > :cursor`) is dead — which makes the O(n²) concern in §d.3's own rejected-alternatives table live again
- `opencode agent list` → **`opencode debug agents`** (JSON by default, no `--format` flag), subject to the scoping caveat above

Still present: `session list --format json --max-count/-n` (default **100**), `session delete`, `session import`, `stats`, `api`, `debug {agents,config,paths}`, `models`. `opencode run` keeps `--session/-s` (documented as "Session ID to continue, **or to create if it does not exist**"), `--fork`, `--title`, `--agent`, `--model/-m` (`provider/model#variant`), `--format {default,json}`, `--continue/-c`, `--auto`.

`session list` records are `{created, directory, id, projectId, title, updated}` — note `projectId`; `directory` survives, so `get_opencode_session_id`'s existing field access still works. NEW-9 holds: v2 help text says "List top-level sessions in the current **project**".

---

## Ticket-family findings that survived revalidation

Verified against `master @ ef4b4df`. All are encoded in MNT-251.

### The `agent_sessions` DDL cannot be created as written

MNT-246 migration 1 declares `id uuid PRIMARY KEY` plus `UNIQUE (task_id, session_id)`; migration 2 declares `session_history.agent_session_id` as a FK to `agent_sessions.session_id`. Postgres requires an FK to reference a primary key or a column set carrying its own UNIQUE constraint — `session_id` alone has neither, so `ADD CONSTRAINT ... FOREIGN KEY` **fails**. The design conflates the surrogate key with the opencode session id. Fix: point the FK at `agent_sessions.id`. Nothing in the proposed DDL constrains `is_primary` to one row per task either.

### `kind DEFAULT 'step'` silently zeroes every existing session's total

Combined with §d.7's "`_compute_total_tokens` sums only `kind='invocation'`", the DDL retroactively drops all **632** legacy rows — including every populated `plan`/`build`/`completed`/`failed` row — out of every existing total. NEW-16 establishes these rows cannot be recomputed. Migration must backfill `kind='invocation'` where any token column is non-NULL.

### `update_session_step` preserves the research no-op

**File:** `demetra/services/persistence/database.py:752` — inserts a history row only `if session_id:`. Research never sets `sessions.session_id` (no plan step runs; `research.py:92,230` pass `context.session_id`, which is `""`), so research produces **zero** rows. §d.2's "exactly as today via `update_session_step`" cannot satisfy the acceptance criterion "a research-only task gets a non-empty history".

### `setup.py` is not a choke point

`setup_workflow` has exactly one caller: `main.py:91`. `run_merge_workflow`, `run_rebase_workflow` and `run_review_fixes_workflow` are dispatched directly by the listener daemon (`services/daemons/listener.py:230-234`) and create their own worktrees (`merge.py:86`, `rebase.py:84`, `review_fixes.py:220`) — they never execute `setup.py`. Research returns at `setup.py:87-95`, **before** the worktree block at 97-108. MNT-251's original claim that one check in `setup.py` covers all nine agents was false for four of them. Put the check where the agent is invoked — inside `run_opencode_agent`.

### merge / rebase / review_fixes are in the rule but absent from the build plan

§d.2 lists them as agent steps; §f build step 6 lists only `plan.py, build.py, validate.py, review.py, research.py, resolve.py`. All three invoke real LLM agents (`review_fixes.py:254`, `opencode_merge_agent`, `opencode_rebase_agent`) and write **zero** history rows today. They also create and destroy their own worktree inside the flow, so the export must be read **before** `git_worktree_remove`.

### Review's per-model rows have no implementation path

**File:** `demetra/workflows/review.py:26-86` returns a single summarized `str | None`; the per-model `(exit_code, stdout, stderr)` tuples from `asyncio.gather` are consumed and discarded at lines 63-74. §d.2/NEW-11 prescribe one session per (round, model), which needs structured per-model results plus a round counter that exists nowhere in the build loop. Note `review.py:55-59` fires `len(review_models)` (default 3, `settings.py:171`) concurrent agents into the **same** `--dir` — never thread one shared session id through them.

### The immutable pointer contradicts the stale-session fix

**File:** `demetra/services/persistence/database.py:211` and `:469` — both writers use `session_id = COALESCE(NULLIF(EXCLUDED.session_id,''), sessions.session_id)`, so the column can never be replaced or cleared (NEW-10). §d.5's retry-without-`--session` yields a **new** primary id that can never be written back, while `api/sessions.py:70` resolves exactly that column and `SessionArtifacts.tsx:135` gates on `!!session.session_id`. After one worktree deletion the task's history 404s and "View History" disappears permanently — the [[2026-08-19-build-agent-stale-session-deleted-worktree]] incident survives the redesign. v2's `--session` semantics ("or to create if it does not exist") make the pointer-replaceable option cheaper.

### Invalidation belongs in the workflow, not the VCS service

§d.5 places the `agent_sessions` invalidation at `git.py:477-517`. `services/vcs/git.py` has **zero** session or DB references today; adding a persistence write there violates AGENTS.md's strict layering. `cleanup_workflow` (`cleanup.py:145-183`) is the caller and the correct home.

### `--format json` would wreck the operator's live view and the session logs

`run_command` defaults `disable_stdio=False`, and `live_stream` (`services/runtime/utils.py:82-107`) writes every line to `sys.stdout` **and** to `stream_logger`, which `setup_session_logging` (`utils.py:149-174`) routes into `LOG_DIR/sessions/<task_id>.log`. Post-migration both fill with raw NDJSON, and `plan.py:92` still prints `"Plain plan agent output:\n{plan_output}"`. MNT-244 just shipped a step-animation UI over this stream.

### Smaller items re-verified

- **`has_tokens` divergence (NEW-12)** — backend `api/sessions.py:110` checks 5 token fields, frontend `SessionHistory.tsx:32-40` checks 8 including `context_tokens`, `model`, `length`. Real, but the NULL token columns that motivated it come from the broken export, not only the predicate.
- **`awaiting_input` double-write (NEW-5)** — `plan.py:47` passes `session_id`, defeating the deliberate omission at `cleanup.py:164`. Drop the argument.
- **Ordering (NEW-14)** — `get_session_history` (`database.py:881`) orders by `created_at` only and `id` is a random uuid4, so there is no real tiebreak. Needs `ORDER BY created_at, id`.
- **Terminal rows mis-attribute the model (NEW-13)** — `cleanup.py:131` and `:176` hardcode `opencode_build_model`.
- **Cascade (NEW-17)** — `delete_session` (`database.py:2131-2168`) deletes the `sessions` row and log file but no history rows; cascading via `agent_session_id` covers invocation rows only, leaving `kind='step'` rows orphaned.
- **Watcher gate** — `get_pending_session_task_ids` (`database.py:926-935`) filters `session_id == ""`, which also misses NULL. §d.6's `NOT EXISTS (SELECT 1 FROM agent_sessions ...)` is right, else plan-only and research-only tasks stay pending forever.
- **Plan-loop stale session id** — `plan.py:118` guards the lookup on `not context.session_id`, so in `--plan-loop` mode iteration 2 never re-resolves and the persisted id keeps pointing at plan session #1.
- **MNT-245 prose error** — claims `record_session_step_history` has three call sites; there are **four** (`plan.py:149`, `build.py:39`, `cleanup.py:127`, `cleanup.py:172`). MNT-246 §b states it correctly.
- **MNT-234 bogus cross-reference** — cites "the open MNT-151 follow-up" as "the single highest-value fix in this area". MNT-151 is *Switch to Redis, remove Kafka* in the unrelated `coruscant` project. Corrected on the ticket.

---

## What was ruled out

- **That production is already broken on v2.** It is not. Production runs **1.18.30**, where `export`, `db`, `agent list`, `run --dir` and `run --command` all still work — which is why MNT-246 could read tokens and query the histogram at all. So the epic's **6.4× over-report is the current live state**, not a stale 1.x artifact, and the v2 breakage is one `make docker-build` away rather than already present. (This bullet originally claimed the opposite; corrected at 14:14 after measuring the actual binary.)
- **That `opencode debug agents` can gate agent resolution.** It returns `[]` outside a project with local agents while the global agents resolve fine at run time — proven by `info.agent = "validate-agent"` from exactly such a directory.
- **That forks double-count the parent's tokens.** They don't; `info.tokens` restarts. The opposite error (under-counting to zero) is the real trap.
- **That NEW-8's uniform 64 KB pipe cap still applies.** `session list` piped 140,107 bytes cleanly. The cap is subcommand-specific — `session export` truncated at exactly 6 × 65,536.
- **That the agent-fallback defect needs new detection code.** v2 hard-fails with exit 1, so existing error paths already surface it.
- **That per-message token sums give exact per-step attribution.** They under-count `input` ~4× and are structurally inconsistent on forks.
- **That compaction works.** It does not, on either version — `/compact` is passed as the message positional and reaches the agent as a prompt. Verified on v2 (the `build` agent's reasoning is in the transcript) and on 1.18.30 (routes to `> build · MiniMax-M3`, whereas `run --command compact` takes a different path).

---

## Open questions

1. **Adopt `--format json` at all?** Phase 0 confirmed the schema is usable, but it moves errors from stderr to stdout and exposes the stream to pipe truncation. The fallback is unique `--title` + `session list`, which keeps NEW-9 exposure and title-matching fragility — worsened by the now-confirmed `(fork #1)` title mutation. This is the one remaining go/no-go.
2. **Does `run --format json` truncate on a pipe at production stream sizes?** Still untested at production scale, but the risk is now quantified rather than theoretical: a **single** tool-using turn that read one 33 KB file emitted **73,660 bytes** of NDJSON — already past 65,536. A real build runs up to `MAX_ATTEMPTS["build"]` iterations with many tool calls, so streams will be multiples of that. `session export` truncated at exactly 6 × 65,536, so treat `run --format json` as exposed and make the wrapper file-backed unless a production-sized measurement says otherwise.
3. **Do the internal agents (`compaction`, `summary`, `title`) account for the whole NEW-3 gap?** The fork inconsistency explains part of it; the remainder is inferred, not proven.
4. ~~**Is `info.tokens` monotonic across a `/compact`?**~~ — **RESOLVED 2026-10-16 14:14, measured: yes.** Cumulative rose 61,610 → 79,942 across a real `/compact`, so `max(0, new_cum - cursor)` cannot clamp to zero. No cursor reset or special-casing needed around compaction. Details in the Update below.
5. **How does compaction get invoked on v2 at all?** 1.18.30 has `run --command <name>` for slash commands; **v2's `run` has no `--command` flag**. Candidates: `opencode api` (v2 server API, takes an OpenAPI operation id or `method path`), or drop compaction and rely on the fork-once design to bound context. Undecided — see the Update below.

---

## Update — 2026-10-16 14:14

Three further probes, one of which corrected this page's own framing and two of which found new defects.

### The version premise was wrong — production is on 1.18.30 and works

The original body claimed token accounting was "silently dead" in production. **It is not.** Established by measurement:

- `~/.opencode/bin/opencode` — the `OPENCODE_PATH` default (`settings.py:164`) and the binary `Dockerfile:37` bakes into the image — reports **1.18.30**, and its `run --help` documents `--dir`, `--command`, `--fork`, `--session`, `--format`, `--title`, `--agent`. All the flags Demetra passes exist. `export`, `db` and `agent` also exist on 1.x, which is how MNT-246 could read tokens and query the histogram at all.
- `https://opencode.ai/update/api/latest/cli/npm` — the endpoint `v2/install` resolves at build time — returns `{"channel":"latest","version":"2.0.30"}` with a `time_created` of **today**.
- The `opencode` first on this machine's `PATH` is `~/.bun/bin/opencode` (npm `@opencode/cli`, symlinked today) → **v2.0.30**. Every v2 probe on this page used that binary; the 1.18.30 probes used the explicit `~/.opencode/bin/opencode` path under an isolated `HOME` so the old binary could not touch the shared v2 session store.

So MNT-246's numbers (6.4× overall, 19.1× on the retained window, 632 rows, 94.6% unpersisted) are **current production truth**, not stale. Everything v2-specific on this page is a forward-looking landmine.

### NEW: v2 removed `run --dir`, which every agent invocation passes

```
$ opencode run --dir /tmp --model ... "hi"
ERROR  Unrecognized flag: --dir in command opencode run     # exit 1
```

**File:** `demetra/services/agents/opencode.py:342`

```python
command = [str(OPENCODE["path"]), "run", "--dir", str(target_path), "--model", model, "--agent", agent]
```

On v2 the directory became a **root positional** (`opencode <subcommand> [flags] [<directory>]`), not a `run` flag. `opencode.py:342` is the single call path for **all nine** agent wrappers, and `opencode.py:541-549` (`opencode_compact_session`) passes `--dir` too. So one removed flag takes down plan, build, validate, review, resolve, research, merge, rebase and review_fixes simultaneously.

`run_command` (`services/runtime/subprocess.py:127-133`) already sets `cwd=target_path`, so the flag is redundant and dropping it is the minimal fix on v2 and harmless on 1.x. One thing to verify after the change: `session list` is project-scoped, so session-to-project binding must still derive correctly from cwd.

This is the most time-critical item in MNT-251 — it converts the unpinned-Dockerfile risk from "gradual accounting drift" into "total platform outage at the next `make docker-build`".

### NEW: context compaction has never worked, on either version

**File:** `demetra/services/agents/opencode.py:528-550`

```python
command = [path, "run", "--session", session_id, "--dir", str(target_path), "/compact"]
```

`/compact` is passed as the **message positional**, and on both versions that is delivered to the agent as a *prompt*, not executed as a command.

- **v2** — exit 0, and the `build` agent answered conversationally. Its own reasoning is preserved in the transcript: *"The user invoked /compact. This is a compact command. There's no tool for compaction explicitly. The harness likely handles it, but I should respond a Compact acknowledged"*. No `compaction` agent ran (distinct agents in the session: `['build']`), messages grew by a normal turn (11 → 15), and `context_tokens` did not drop (18,148 → 18,180).
- **1.18.30** — the same form routes to `> build · MiniMax-M3` (an agent plus a model, i.e. a prompt), whereas `run --command compact` takes a visibly different code path. `--command` is documented on 1.18.30 as "the command to run, use message for args" — that is the correct mechanism, and Demetra does not use it.

So every time a build session crosses `CONTEXT_COMPACTION_THRESHOLD`, Demetra pays for a **full-context LLM turn that returns a role-played acknowledgment** and the session keeps growing. `2026-07-07-add-context-compaction.md` records compaction as "live" since `47d428d` (2026-07-23) and its Test Results as "compaction triggering" — the tests assert the subprocess was called, never that the context shrank, which is why this survived three months.

**v2 has no `--command` flag on `run` at all**, so compaction has no CLI path there. Options: `opencode api` (v2 server API, takes an OpenAPI operation id or `method path`), or drop compaction and rely on the fork-once design to bound context. Whichever is chosen, the replacement test must assert `context_tokens` **decreases**, not that the command exited 0.

### Compaction monotonicity — measured, and the delta model is safe

Tracked one session across three exports using a free model (`opencode/deepseek-v4.1-flash-free`, cost 0 throughout):

- **T1 baseline** — `CUM = 25,343`, `context_tokens = 17,861`, 6 messages
- **T2 after a second turn** — `CUM = 61,610`, `context_tokens = 18,148`, 11 messages
- **T3 after `/compact`** — `CUM = 79,942`, `context_tokens = 18,180`, 15 messages

`info.tokens` is **monotonic across compaction** (+36,267 then +18,332, never negative), so `delta = max(0, new_cum - cursor)` cannot clamp to zero after a compact and needs no reset or special-casing. Note this holds *because* the `/compact` above was a no-op turn — the measurement is still valid for the arithmetic, but it should be repeated once compaction genuinely rewrites the session (open question #5).

### Additional v2 schema detail from this probe

`--format json` on a tool-using run emitted event types `step_start`, `tool_use`, `step_finish`, `text` — beyond the `step_start`/`text`/`error` seen earlier. A 1-turn run that read a 33 KB file produced **73,660 bytes** of NDJSON, which is already past the 64 KB multiple that truncated `session export`; a real build will be far larger. Reassembly must skip `tool_use`/`step_start`/`step_finish` and concat only `type == "text"` parts. `messages[]` also carries a `system` type not seen in the earlier probe (observed set: `user`, `assistant`, `idle`, `system`, `agent-switched`).

---

## Follow-ups

- **Most urgent:** drop `--dir` from `opencode.py:342` and `opencode.py:541-549` before any image rebuild, or the platform stops working entirely. MNT-251 Phase 1 step 1.
- **Live bug on 1.18.30:** compaction is a no-op that burns a full-context turn. Fix via `--command compact` on 1.x; decide the v2 mechanism deliberately. MNT-251 Phase 1 step 4.
- MNT-251 Phase 1 is unblocked and independently shippable — it needs no further spike. It is sitting in **PRD**, deliberately not **Todo**, because the watcher polls Linear TODO and would hand the plan agent both phases at once.
- The unpinned Dockerfile install remains an accepted risk, but the blast radius is now known to be total rather than gradual. MNT-251 §12 asks for that decision to be revisited.
- MNT-241 stays **Done** with no implementation landed (`grep -rn "agent_sessions"` returns zero hits). It carries a note naming MNT-251 as the unified ticket it asked for.
- Re-run the monotonicity measurement once compaction genuinely rewrites a session, since the probe above compacted nothing.

---

## References

- Related: [[2026-07-16-session-history-tokens-null]] (the original 64 KB PIPE truncation fix — now known to be subcommand-specific on v2)
- Related: [[2026-08-19-build-agent-stale-session-deleted-worktree]] (the systemic follow-up MNT-251 Phase 2 step 8 must close)
- Related: [[2026-07-23-session-tokens-audit-revalidation]] (cumulative-vs-delta; cache ~96% of tokens)
- Related: [[2026-09-30-mnt-228-intermediate-history-states]] (the two-writer rule `plan.py:47` violates)
- Related: [[2026-08-25-mnt-181-total-tokens-counter]] (`_compute_total_tokens` semantics this changes)
- Related: [[2026-07-23-session-history-modal]] (history endpoint; the `SELECT DISTINCT step` follow-up MNT-245 closed)
- Related: [[2026-07-07-add-context-compaction]] (`CONTEXT_COMPACTION_THRESHOLD`; currently dead code in production)
- Related: [[2026-10-06-unify-subprocess-env-on-session-environment]] (`run_command` / `build_subprocess_env` plumbing)
- External: https://linear.app/mnt/issue/MNT-251 — implementation target, carries the full Phase 0 measurements and corrected build plan
- External: https://linear.app/mnt/issue/MNT-246 — 1.18.35 research record, annotated with the v2 corrections
- External: https://linear.app/mnt/issue/MNT-241 — epic
