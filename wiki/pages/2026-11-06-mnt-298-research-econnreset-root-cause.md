---
title: 'MNT-298 research agent ECONNRESET — local opencode server thrash'
date: 2026-11-06
type: debug
status: resolved
session_id: ses_e4e580613ffenQ8d8seoL46RZe
services: [agents, linear, llm]
branch: master
tickets: [MNT-298]
tags: [network, econnreset, opencode, deepseek, research-agent, managed-service, service.json, debugging]
related: [2026-11-06-agent-econnreset-network-investigation.md, 2026-11-03-mnt-276-econnreset-retry-for-agents.md]
---

# MNT-298 research agent ECONNRESET — local opencode server thrash

## TL;DR

The MNT-298 ("Auto deploy") research workflow kept printing
`Agent research-agent hit a network error (attempt N/10)` and exhausting its
retry budget on `ECONNRESET`. Opening the workflow's opencode session showed the
**DeepSeek model was responding fine** — the reset is a **local** opencode
CLI↔server event-stream drop, caused by concurrent `opencode run` invocations
thrashing a single managed-service registration (`service.json`). Each new run
"replaces" the registration and shuts down the previous server, killing the
in-flight stream. This refines (not contradicts) the earlier
[[2026-11-06-agent-econnreset-network-investigation]] conclusion: the resets are
server-side, but the server in question is **opencode's own local server**, not
`api.deepseek.com`.

---

## Symptom

- `worker.log` / `sessions/5461e169-…log` showed, from 16:15:24 to 16:20:11:
  `Error: Transport: ECONNRESET: The socket connection was closed unexpectedly … fetch()`,
  then `Agent research-agent hit a network error (attempt 1/10 … 7/10); retrying in {2s,4s,8s,…128s}`.
- The research agent is `deepseek/deepseek-v4-pro` (provider `deepseek`, direct
  `api.deepseek.com`), the same model/provider as the interactive session that
  was working at the same time — so the user correctly observed the workflow
  fails while this session does not.

## Step 1 — Resolve the workflow's opencode session

`~/.local/share/opencode/opencode.db` (`session_v2`) has **92** sessions titled
`MNT-298: Auto deploy`, grouped:

- 90 × `minimax/minimax-m3` (`providerID=openrouter`), 15:55:20 → 16:14:23, all
  `tokens_input=0 tokens_output=0` — these failed instantly on an OpenRouter
  **credit limit** (`This request requires more credits … can only afford 197010`),
  i.e. `Research agent failed (exit 1)`, not a network error.
- 1 × `deepseek-v4-pro` (`providerID=deepseek`), `ses_e4e5b56c3ffegz9jgHhCnjjb6F`,
  16:15:21 → 16:27:23, `tokens_input=23876 tokens_output=8324` — this one actually
  generated.

The user-level override in `project_environment` pins `OPENCODE_RESEARCH_MODEL =
deepseek/deepseek-v4-pro` (direct DeepSeek key `sk-b31bd4…` in
`~/.local/share/opencode/auth.json`), switched from OpenRouter after the credit
errors.

## Step 2 — Open the deepseek session and read the message history

`session_message` for `ses_e4e5b56c3ffegz9jgHhCnjjb6F` shows a repeating cycle,
~40–80 s apart:

- `user` — the research prompt (`You are a research specialist …`).
- `assistant` — **real model responses with token counts** (e.g.
  `input 11312 / output 187`, `input 4242 / output 248`).
- `ERROR {type: aborted, message: "Step interrupted"}`.
- `synthetic` — `"The server restarted while you were working. Continue from
  where you left off without repeating completed work."`
- `agent-switched` — then the cycle repeats.

The model never rejected a request; DeepSeek connectivity is not the issue.

## Step 3 — Find the source of the ECONNRESET in the opencode log

`~/.local/share/opencode/log/opencode.log` contains the exact string Demetra
captured, but tagged as a **local client stream**, not an upstream API call:

- `message="event stream disconnected" component=client attempt=1 error="Transport: ECONNRESET: The socket connection was closed unexpectedly …" role=cli`

Immediately before every such event is its cause:

- `message="managed service registration replaced; shutting down" serviceID=… servicePID=… observedServiceID=… observedServicePID=… observedURL=http://127.0.0.1:49374`

Correlated 1:1 at 16:18:45.605/16:18:45.608, 16:20:05.958/16:20:05.960,
16:22:26.278/16:22:26.279, 16:27:01.785/16:27:01.787, and many more every ~5–60 s.

## Root cause

Every `opencode run` process registers a background "managed service" in
`~/.local/state/opencode/service.json` (one file, one URL
`http://127.0.0.1:49374`). When a new `opencode run` starts while another is
still active, its registration **replaces** the old one and the old server is
shut down (`managed service registration replaced; shutting down`). The old
CLI's event stream to its server is dropped, surfacing as
`Transport: ECONNRESET` — which Demetra's `is_network_error()`
(`demetra/services/agents/opencode.py:313`, marker `ECONNRESET`) classifies as a
transient network error and retries.

The thrash is driven by concurrency, not DeepSeek:

- MNT-298 never completes, so the watcher re-picks it up roughly every 60 s
  (`→ Retrieved task: MNT-298: Auto deploy`) and spawns a fresh `opencode run`.
- Demetra's internal retry loop also spawns `opencode run --session …` on each
  attempt.
- Other tickets (e.g. the `mnt-286-…` worktree in the log) and multiple workers
  (`--scale worker=2/4`) run concurrently, all sharing one managed-service
  registration.

Why this session survives: the interactive session is resumed transparently
across a server replacement (that is exactly the "The server restarted…
continue" message this session also receives), whereas a headless one-shot
`opencode run` exits non-zero with the ECONNRESET in stderr.

## Resolution / Fix

- Added `--standalone` to the agent invocation so every `opencode run` uses its
  own **private server** instead of the shared background managed service
  (`demetra/services/agents/opencode.py:697`; assertions updated in
  `tests/test_opencode.py`, 84 passed). This kills the `service.json`
  registration thrash outright — no per-replica `XDG_*` isolation needed.
- The MNT-276 retry layer was the wrong tool here: raising
  `MAX_AGENT_NETWORK_ATTEMPTS` cannot fix a local server-registration thrash.
- Confirmed the ECONNRESET in [[2026-11-06-agent-econnreset-network-investigation]]
  is server-side but **local** — revise that page's "DeepSeek idle-close" theory
  as the primary mechanism (DeepSeek's ~30 s idle close may still be a secondary
  contributor, but it is not what MNT-298 hit).

## Known follow-up (not fixed this session)

- ~~Give each worker/`opencode run` its own service state dir / serialize~~
  — fixed with `--standalone`; still worth watching for SQLite (`opencode.db`)
  lock contention since every run still shares one `opencode.db`.
- Add a per-ticket in-progress guard so the watcher doesn't re-spawn
  `opencode run` while a prior attempt is still retrying.
- Re-authenticate the Linear MCP (`needs_auth`) and fix the Demetra MCP
  `.env.docker` path in worktrees — both block the research agent's tooling
  independently of the ECONNRESET.
- Confirm the OpenRouter monthly credit limit (the 90 × minimax failures) is
  raised or the research model stays pinned to direct DeepSeek.

---

## Update — 2026-11-06 16:45

Confirmed the mechanism in `docker-compose.yaml`: the workers are **not**
isolated at the filesystem level.

- `docker-compose.yaml:22` mounts the shared named volume
  `demetra_app_data:/home/demetra/` on every `*demetra-app` service (`api`,
  `worker`, `watcher`, `listener`). The opencode state lives under
  `/home/demetra/` (`Dockerfile:52-58`: `useradd -d /home/demetra demetra`,
  state in `/home/demetra/.config/opencode` + `/home/demetra/.local/share/opencode`),
  so it is on that shared volume.
- `worker.deploy.replicas: 2` (`docker-compose.yaml:116`); `make deploy` runs
  `--scale worker=2` (`Makefile:31`), `make docker-up` runs `--scale worker=4`
  (`Makefile:101`).
- Everything that spawns `opencode run` — every worker replica, the watcher,
  the listener — therefore reads/writes the **same**
  `/home/demetra/.local/state/opencode/service.json` and the same
  `opencode.db` (SQLite), snapshots and worktrees.
- Because each container has its own loopback, `service.json`'s
  `observedURL=http://127.0.0.1:49374` can never be reused across containers, so
  every new `opencode run` "replaces" the registration and the previous server
  (in another container) detects it and shuts down → the ECONNRESET thrash.

Isolation today is only process/network (separate containers, separate loopback)
plus the single-file `auth.json` bind-mount (`.keys/opencode/auth.json`,
`docker-compose.yaml:29`); the opencode state itself is shared.

## Update — 2026-11-06 19:54

Implemented the fix and verified it.

- `opencode --help` exposes `--standalone` — "Run with a private server instead
  of the background service". `opencode run --standalone …` parses correctly
  after the subcommand (verified via `--help`, exit 0).
- `demetra/services/agents/opencode.py:697` now builds
  `["run", "--standalone", "--model", …, "--agent", …]`; `run_opencode_agent`
  was the single place all agent wrappers (plan/build/review/validate/resolve/
  research/merge/rebase) funnel through, so one edit covers them all.
- `--standalone` also fixes the parallel review agents
  (`workflows/review.py:65-82` runs one `opencode run` per model concurrently):
  each gets its own private server, no shared registration.
- `tests/test_opencode.py`: the three exact-command assertions gained
  `"--standalone"`; full file passes (84 passed). `ruff check` clean.
- Session accounting is unaffected in principle — `--standalone` changes the
  *server*, not the data dir, so sessions still land in the shared
  `opencode.db` and `session list`/`export` (used by `capture_agent_session`)
  still resolve them. End-to-end still to be confirmed on a real run.

## Follow-ups

- See "Known follow-up" above.

> **Consistency note (2026-11-09, Consistency Agent):** two facts above are time-bound. (1) The incident logs quote `attempt N/10` and the page says the retry budget was "exhausting", but the shipped default since MNT-276 (`eeec893`) is `MAX_AGENT_NETWORK_ATTEMPTS = 5` (`demetra/settings.py:61`; `.env.docker.example` does not override it) — the 10-attempt run implies an environment override at the time, tracked as **Q-003** in `wiki/QUESTIONS.md`. (2) "opencode.py:697 now builds `["run", "--standalone", …]`" is unconditional in wording; the implemented code probes first (`opencode_supports_standalone`, `demetra/services/agents/opencode.py:646-676`) and only appends `--standalone` when `run --help` advertises it (`:741`), so older CLIs are not broken.

## References

- Related: [[2026-11-06-agent-econnreset-network-investigation]]
- Related: [[2026-11-03-mnt-276-econnreset-retry-for-agents]]

> **Consistency note (2026-11-11, Consistency Agent):** Update to the 2026-11-09 consistency note above: the “10-attempt budget vs shipped default of 5” discrepancy (**Q-003**) is **resolved** — production carried an environment-level override (`MAX_AGENT_NETWORK_ATTEMPTS=10`, `AGENT_NETWORK_BACKOFF_BASE=2`, `.env.docker:17-18`), confirmed by `wiki/postmortems/2026-11-09-econnreset-incident-postmortem.md`. The repository default stays 5 (`demetra/settings.py:61`); the `attempt N/10` logs and the shipped default were never in conflict. The second item in the 2026-11-09 note (the `--standalone` probe) still holds.
