# ECONNRESET agent incident (Oct 27 – Nov 9, 2026)

## TL;DR

For about two weeks (2026-10-27 → 2026-11-09), background agent runs (`plan`,
`build`, `validate`, `review`, `research`) intermittently died mid-stream with
`Error: Transport: ECONNRESET` / `Error: Connection lost while reading the
response: ECONNRESET`. The window saw **278 distinct error events** across
**10 tickets**, four recorded budget-exhaustion failures and repeated
`Awaiting Input` round-trips. Two independent mechanisms were ultimately
identified: server-side idle closes on long-lived LLM-provider connections,
and — the more damaging one — a local opencode managed-service registration
thrash between concurrent `opencode run` invocations sharing the same
`service.json`. Resilience was addressed by the MNT-276 retry layer (merged
Nov 3, operating with an env-level override of 10 attempts / 2 s backoff base)
and the root cause of the research-agent family was fixed by running every
agent with `--standalone` (committed Nov 9); a research-loop guardrail
(MNT-299) and a run-attempt reset fix landed the same day. The fixes were
carried live by the stack recreation of Nov 10 09:13 UTC.

## Summary

- **Scope**: all background agent runs (`opencode run` invocations spawned by
  the Demetra worker/watcher/listener), any agent kind, any model.
- **Window**: 2026-10-27 06:55 UTC (first recorded event) → 2026-11-09/10
  (mitigations deployed with the Nov 10 stack recreation).
- **Assessment**: retries absorbed most events; the residual failures were
  ticket-level stalls (budget exhaustion / repeat `Awaiting Input`), not data
  loss or bad merges.
- **Environment**: Docker compose stack (`worker` replicas ×2, `watcher`,
  `listener`), agents running `opencode` against paid providers
  (`api.deepseek.com` direct, OpenRouter), repo bind-mounted into the
  containers.

## Impact

- 278 unique error events (`ECONNRESET` mid-stream stderr events, deduplicated
  per timestamp; snapshot taken 2026-11-10 ~13:00 UTC across all rotated
  `worker.log*` files).
- Ticket-level effects: plan/build/review agents failed, retried, or exhausted
  their network budget. Affected work: CH-1 (video enrichment), CH-2 (session
  view), MNT-260, MNT-276's own dogfooding, MNT-261, MNT-270, CH-4/CH-6 build
  work, the MNT-298 research loop (re-spawned roughly every 60 s for hours),
  CH-7/CH-8 (this postmortem's own workflow failed on the first build attempt,
  Nov 10, with a related but distinct "Nothing to compact yet" error — MNT-305).
- Workflow consequences: tickets moved to `Awaiting Input` (the
  `agent_network_failed` Linear comment), review round-trips repeated, and the
  MNT-298 research loop occupied workers without progress.

## Root cause

Two mechanisms, plus amplifiers. All three are stated as system conditions, not
individual actions.

1. **Server-side LLM-provider idle closes.** Idle-hold tests from inside the
   container (Nov 6) showed the providers themselves drop long-lived
   connections: `api.deepseek.com` closes at ~30 s idle, the
   `opencode.ai`/Cloudflare edge at ~15 s, while a Google control connection
   stayed alive 80 s. When the OpenCode CLI reuses a stale keep-alive
   connection the server has already closed, the stream fails immediately with
   a mid-stream reset. Clustered retries failing over ~90 s also pointed to
   transient provider-side outages at those moments. This was the primary
   explanation for the mid-stream CH-1–CH-4 resets.
2. **Local managed-service registration thrash.** Every `opencode run`
   registers a managed service in a single `service.json`. Concurrent
   invocations (multiple worker replicas, watcher re-picks, per-attempt re-runs)
   *replace* that registration, and the old server shuts down
   (`managed service registration replaced; shutting down`), dropping the
   in-flight event stream — which surfaces as the same `ECONNRESET` in stderr.
   Because each container has its own loopback, cross-container reuse is
   impossible, so replacement happens on every concurrency overlap. This was
   the actual driver of the MNT-298 research-agent family; headless one-shot
   runs exit non-zero on it, while interactive sessions survive transparently.
3. **Amplifiers.**
   - Every `*demetra-app` service mounts the same `demetra_app_data` volume,
     so the opencode state (and the shared `opencode.db`) is one shared surface.
   - The watcher had no per-ticket in-progress guard, so a ticket stuck in
     retrying state kept being re-picked every ~60 s, multiplying concurrent
     runs.
   - The retry budget counted the wrong layer for mechanism 2: raising the
     attempt count cannot fix a local server-registration thrash.

The network environment was cleared first during the investigation: host NIC,
bridges and veths were all at MTU 1500 (no mismatch; a 10 MB transfer completed
cleanly), IPv6 had no global route (hygiene issue, later disabled in
`docker-compose.yaml`), and the models involved were all paid — so the
free-tier gateway was not involved.

## Timeline

All times UTC (the `+03:00` commit timestamps converted).

- **2026-10-27 06:55** — first recorded `ECONNRESET`: a plan agent died
  mid-stream during the plan workflow; further agent failures the same day at
  07:12 (build) and 11:34 (plan). 23 unique error events on the day.
- **2026-10-29** — single-second cluster; the problem is intermittent and
  treated as provider noise rather than tracked.
- **2026-11-02** — cluster during CH-1 plan/build work and dogfooding of the
  so-far-unmerged MNT-276 branch: 14:02 the first recorded budget-exhaustion
  terminal failure (`AgentNetworkError`), 14:03 and 18:47 plan agents died
  outright (pre-MNT-276 code paths), 19:54 a build-agent failure. 36 unique
  events on the day.
- **2026-11-03** — MNT-276 merged (PR #148, 13:02). `run_opencode_agent` now
  retries transient network errors with exponential backoff, resuming the
  failed attempt's session; exhaustion raises a typed `AgentNetworkError` and
  posts the `agent_network_failed` comment ending in `Awaiting Input`, without
  marking the ticket failed. Production ran with an environment-level override
  of `MAX_AGENT_NETWORK_ATTEMPTS=10`, `AGENT_NETWORK_BACKOFF_BASE=2`
  (shipped defaults: 5 attempts, 1.0 s base). 60 unique events — the heaviest
  full day before the Nov 9 peak, all absorbed by the retry loop.
- **2026-11-05** — CH-4 build agent exhausted its budget at 19:21; 9 unique
  events; the formal network investigation session opened (first wiki debug
  record).
- **2026-11-06** — investigation day, 55 unique events. Morning:
  docker-compose network settings updated (09:58); Docker image rebuilt
  (11:30 image timestamp). Afternoon: IPv6 disabled in containers plus a
  `dns:`/TCP-keepalive sysctl hygiene change (12:31). 16:15–16:35: the
  MNT-298 research agent hit its own `ECONNRESET` cluster and exhausted the
  budget (16:35 terminal failure) while the interactive session at the same
  moment worked fine — this contradiction opened the second root cause.
  Session-level correlation against the opencode local log proved the
  `managed service registration replaced` → `event stream disconnected`
  mechanism 1:1.
- **2026-11-09** — mitigation day, but the largest raw burst: 84 unique events
  concentrated 19:00–23:00, because the long-running worker processes still
  served pre-fix code from memory. Commits: 15:44 `--standalone` for every
  agent run (`b59e193`); 16:18 run-attempt reset gating (16:18); 18:11 the
  MNT-299 research-loop guardrail merged (PR #154).
- **2026-11-10 07:00–08:04** — residual retries around CH-7 review agents;
  08:04 the CH-7 build agent failed with a distinct "Nothing to compact yet"
  error (tracked under MNT-305, not a `ECONNRESET`).
- **2026-11-10 09:13** — stack recreated; worker processes now run the
  `--standalone` + guardrail code. 10 unique events observed in the partial
  morning before the snapshot (09:00–13:00), from the same morning window, not
  after the restart.

## Detection

- Noticed through `worker.log` stderr and repeated
  `agent_network_failed` comments on tickets — high noise, initially read as
  provider flakiness ("works in the TUI at the same time", "different ISPs/pins
  no improvement") which early on steered the diagnosis inward, then outward,
  then back to local.
- Formal detection came from two records: the per-ticket session logs
  (28-session correlation) and — the decisive proof — opening the workflow's
  opencode session and correlating `event stream disconnected` events in
  the local opencode log with `managed service registration replaced` a few
  ms earlier.
- No metric, alert, or dashboard existed for transport errors; every detection
  step was manual log archaeology.

## Lessons learned

**What went well**

- The MNT-276 retry layer stopped single-shot failures quickly and, once
  deployed, absorbed entire clusters (Nov 3, Nov 6): the design even resumed
  the failed attempt's session instead of restarting the whole prompt, saving
  tokens and time.
- The failure-machinery design decision (typed error + `Awaiting Input`, never
  "failed") kept incident tickets honest and recoverable.
- The wiki debug records preserved the full evidence chain — including the
  intermediate (rejected) hypotheses (ISP, MTU, free-tier gateway, IPv6) —
  which made the postmortem corrections cheap instead of folk-memory
  rewriting.

**What went wrong**

- Diagnosis took ~2 weeks over three waves: links to the local network
  (ruled out by tests), provider idle closes (real but secondary for the
  worst-affected family), and finally the local managed-service thrash. The
  provider hypothesis was plausible, supported by failed-follow-timeouts, but
  opening the actual opencode session proved immediately decisive.
- The first-family assumption that resetting connections were between the app
  and the provider; the real server for one family was inside our own Docker
  network. "Which exactly did the log's `ECONNRESET` terminate?" (client-to-
  provider vs client-to-local-server) is the one question that would have cut
  days.
- Configuration drift: production ran an undocumented attempt-budget override
  (10/2 vs shipped defaults 5/1.0). Recorded as a question in the wiki at the
  time; the override is confirmed here as an environment-level deliberate
  value, but it was invisible in `.env.docker.example` and reached neither
  code review nor migrated documentation.
- State sharing: all worker replicas share the `demetra_app_data` volume and
  the single `opencode.db`, so nothing in the compose file reflects the
  concurrency assumptions of the tooling (`service.json`).
- Long-running workers serve the code they started with, during a bind-mounted
  repo: the Nov 9 fix existed on disk hours before it took effect, and the
  evening burst happened exactly in that gap.

**Where we got lucky**

- Interactive TUI sessions survive server replacement, so users never saw
  broken interactive flows — the incident stayed inside the background
  workflows.
- The failed research runs (90 × minimax in the MNT-298 window) failed
  instantly on a credit-limit error rather than founding their own retry
  loops, which preserved the correlation shape and made the concurrency
  mechanism visible almost immediately.

## Action items

None of these are ticket-tracked yet; they live here until filed.

1. Watch the first full clean day after the Nov 10 stack recreation: confirm
   `--standalone` probing appears in agent command construction and the
   `ECONNRESET` rate drops to zero, then keep the 278-event baseline as the
   reference for regression detection.
2. Add a per-ticket in-progress guard so the watcher does not re-spawn an
   agent run while a prior attempt is still retrying (the MNT-299 guardrail
   covered the research loop; the general path remains open).
3. Document `MAX_AGENT_NETWORK_ATTEMPTS` / `AGENT_NETWORK_BACKOFF_BASE` in
   `.env.docker.example` (or fold the production values into the defaults) so
   the shipped defaults match what production runs.
4. Add transport-error observability: count `ECONNRESET` stderr events per
   ticket and per day (the counting rule below is available as a one-liner)
   and alert on clustering — no manual log archaeology as detection.
5. Watch SQLite contention on the shared `opencode.db` now that every agent
   uses a private server; Shard data-dir isolation is no longer needed, but
   the DB remains one shared file.
6. Consider routing DeepSeek through the OpenRouter gateway (single
   connection-management surface), and tune opencode keep-alive sizing
   against the observed ~15–30 s provider idle closes as a secondary measure.

## Supporting information

### Measurement basis

- **Source**: `/var/log/demetra/worker.log*` (current + 7 rotations) — agent
  stderr is logged there.
- **Counting rule**: lines matching
  `Error: Transport: ECONNRESET` **or**
  `Error: Connection lost while reading the response: ECONNRESET`,
  deduplicated per distinct timestamp (one physical stderr burst is logged
  several times by the worker — full line, wrapped line, and a wrapped re-log):
  728 raw matches → **278 unique events**, 2026-10-27 → 2026-11-10 13:00 UTC.
- One-liner:

  ```sh
  cd /var/log/demetra && { cat worker.log worker.log.1; for f in worker.log.??.gz; do zcat $f; done; } \
    | grep -E 'Error: (Transport: ECONNRESET|Connection lost while reading the response: ECONNRESET)' \
    | cut -c1-23 | sort -u | wc -l
  ```

- Per-day unique events (the first date figures follow):

  | Day | Events |
  | --- | --- |
  | 2026-10-27 | 23 |
  | 2026-10-29 | 1 |
  | 2026-11-02 | 36 |
  | 2026-11-03 | 60 |
  | 2026-11-05 | 9 |
  | 2026-11-06 | 55 |
  | 2026-11-09 | 84 |
  | 2026-11-10 (→ 13:00) | 10 |

- Per-ticket attribution (approximate: each unique event was attributed to the
  most recently *started* `agent_sessions` run within 30 minutes; ~25% stayed
  unattributed because retries resume sessions without fresh run rows):
  CH-8 52, CH-1 46, MNT-276 45, CH-7 19, MNT-298 18, CH-6 11, MNT-260 9,
  CH-2 5, MNT-308 2, MNT-311 1.
- Per-agent attribution (same rule): plan-agent 80, validate-agent 59,
  review-agent 48, research-agent 19, build-agent 2.
- Terminal failures recorded in `session_history` (8 rows): 2026-10-27 06:55,
  07:12, 11:34; 2026-11-02 14:02 (first `AgentNetworkError`), 14:03, 18:47,
  19:54; 2026-11-06 16:35 (research-agent).

### Sessions hit per ticket

Session-level hit counts as captured in the worker log (approximate, same
methodology as above; counts only, no session links — sessions rotate out with
the log files):

- CH-8: 52
- CH-1: 46
- MNT-276: 45
- CH-7: 19
- MNT-298: 18
- CH-6: 11
- MNT-260: 9
- CH-2: 5
- MNT-308: 2
- MNT-311: 1

### Configuration at the time

- Env-level override (confirmed from the running containers on 2026-11-10):
  `MAX_AGENT_NETWORK_ATTEMPTS=10`, `AGENT_NETWORK_BACKOFF_BASE=2`
  (`.env.docker`; shipped defaults in `demetra/settings.py:61-62` are 5 / 1.0).
- Fix code as of the snapshot: retry layer `demetra/services/agents/opencode.py`
  (`NETWORK_ERROR_MARKERS`, `is_network_error`, retry loop), `--standalone`
  probing `opencode_supports_standalone` appending the flag when the CLI
  advertises it (so older CLIs are not broken), failure handler
  `demetra/workflows/failure.py:process_agent_network_failure` with the
  `agent_network_failed` template.

## Follow-ups and References

- [[2026-11-03-mnt-276-econnreset-retry-for-agents]] — the retry layer
  implementation page.
- [[2026-11-06-agent-econnreset-network-investigation]] — the network tests,
  provider idle-close evidence, and the IPv6/MTU clearance (its root-cause
  section is superseded for the research-agent family by MNT-298 — see its
  consistency note).
- [[2026-11-06-mnt-298-research-econnreset-root-cause]] — the local
  managed-service thrash, the `--standalone` fix and its verification.
- MNT-276 ticket: https://linear.app/mnt/issue/MNT-276/econnreset-retry-for-agents
- Commits: `b59e193` (`--standalone`), `4ac7b5f` (run-attempt reset gating),
  `61f5262` + `83c7b90` (compose network hygiene), PR #148 (MNT-276), PR #154
  (MNT-299 research guardrail).
- Post-incident residue: MNT-305 ("Nothing to compact yet") — the distinct
  failure shape observed on 2026-11-10 08:04.
- Open question on the budget discrepancy: Q-003 in
  [[2026-11-06-mnt-298-research-econnreset-root-cause]] (`wiki/QUESTIONS.md`);
  this postmortem's Summary states the resolution: the 10-attempt budget was
  an environment-level override, not a code default.
