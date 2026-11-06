---
title: 'Agent ECONNRESET network errors — root cause'
date: 2026-11-06
type: debug
status: resolved
session_id: ses_e4fc54fc9ffe57ihg20tF1IUDs
services: [agents, deploy, llm]
branch: master
tickets: [MNT-276]
tags: [network, econnreset, docker, llm, openrouter, deepseek, ipv6, mtu, debugging]
related: [2026-11-03-mnt-276-econnreset-retry-for-agents.md]
---

# Agent ECONNRESET network errors — root cause

## TL;DR

Agents across the CH-1–CH-4 sessions (Nov 2–6) intermittently died with
`Error: Transport: ECONNRESET … fetch()` — a mid-stream reset, not a connect
failure. Network tests proved the reset is **server-side** (the LLM providers'
own connection timeouts), not the user's ISP, Docker, or MTU. The root cause is
external to Demetra; the fix is to keep the MNT-276 retry, raise its budget, and
clean up a couple of config nits (IPv6, MTU) that are unrelated but worth fixing.

---

## Symptom

`opencode` runs failed on `ECONNRESET` across every agent kind (plan, build,
review, validate) and provider, spread over Nov 2–6 and all hours. The CH logs
carry the error at scale:

- CH-1 — 31 hits (build-agent exhausted 5 retries on Nov 3 15:38; review-agent
  recovered on attempt 4 on Nov 6 08:51).
- CH-2 — 15 hits (plan-agent failed outright on Nov 2, before MNT-276 landed).
- CH-4 — 76 hits (build-agent exhausted 5 retries on Nov 5 19:21).

Two error shapes appear, both mid-stream:

- `Error: Transport: ECONNRESET: The socket connection was closed unexpectedly …`
- `Error: Connection lost while reading the response: ECONNRESET …`

The user reported trying different ISPs and VPNs with no improvement, which was
the first hint this was not a local-network problem.

## Step 1 — Scope the errors across sessions

Git history and the wiki show the retry layer already exists:

- [[2026-11-03-mnt-276-econnreset-retry-for-agents]] — `run_opencode_agent`
  retries transient network failures (`ECONNRESET`, `socket hang up`,
  `ETIMEDOUT`) with exponential backoff (5 attempts), raising `AgentNetworkError`
  on exhaustion.
- `83c7b90` (same day) — added `dns: [1.1.1.1, 8.8.8.8]` and TCP-keepalive
  sysctls to `docker-compose.yaml`; this targets DNS/NAT and, per the tests
  below, does not address the actual cause.

The failing models (from `project_environment` for `manti.by@gmail.com`) are all
paid, so the free-tier `opencode.ai` gateway is **not** the culprit:

- `OPENCODE_BUILD_MODEL` / `OPENCODE_VALIDATE_MODEL` — `deepseek/deepseek-flash` → `api.deepseek.com`
- `OPENCODE_PLAN_MODEL` / `OPENCODE_RESEARCH_MODEL` — `openrouter/minimax/minimax-m3`
- `OPENCODE_REVIEW_MODELS` — `openrouter/z-ai/glm-5.3`, `openrouter/minimax/minimax-m3`, `deepseek/deepseek-v4-pro`
- `OPENROUTER_MODEL` — `meta-llama/llama-3.3-70b-instruct` (user-level override)

## Step 2 — Network tests (idle-hold, streaming, control)

Ran from inside the container (only `python3`/`bun` available; no `curl`/`ip`).

- **Idle-hold control**: a TLS connection to `google.com` stayed alive 80s with
  no reset — proving the container → host → ISP egress does **not** aggressively
  reset idle connections.
- **Idle-hold providers**: `api.deepseek.com` closed after 30s, `opencode.ai`
  (Cloudflare) after 15s, `github.com` after 5s — these are the servers' own idle
  timeouts, not a middlebox.
- **Streaming**: `api.deepseek.com` (deepseek-chat) returned 200 with clean
  streams repeatedly; a 22s/5.3k-chunk essay stream had zero gaps. The 6-minute
  monitor saw no resets on DeepSeek, and `opencode.ai` free models returned 429
  (rate limit — separate symptom).
- **Large transfer**: a 10 MB download completed in 3.7s with no stalls, ruling
  out a path-MTU problem.

## Step 3 — Rule out MTU / IPv6 / DNS

- **MTU**: the user had changed the host MTU to 1400 "a few days ago", but
  `ip link show` on the host now shows `enp0s31f6` (physical NIC), all Docker
  bridges, and all veths at **1500** — consistent, no mismatch. The 1400 change
  never persisted.
- **IPv6**: enabled in the kernel but with no global route (only `::1`), while
  `opencode.ai`, `openrouter.ai`, `api.openai.com` advertise AAAA records — so
  every connect pays a futile IPv6 "network unreachable" attempt before falling
  back to IPv4. Hygiene issue, not the reset cause.
- **Tailscale**: the `ts.net` search domain is present but `tailscale0` is not
  up — the host is not currently running Tailscale.

## Root cause

**The LLM providers reset long-lived connections server-side.** The resets are
not from the user's network (Google control stayed alive), not from MTU (no
mismatch, large transfers clean), and not from the free tier (all configured
models are paid DeepSeek/OpenRouter). The most likely mechanism is a **stale
keep-alive connection**: the OpenCode CLI's fetch pool reuses a connection the
server already closed (DeepSeek ~30s, Cloudflare ~15s), getting an immediate RST;
clustered retries failing over ~90s also points to transient provider-side
outages at those moments.

## Resolution / Fix

- Disabled IPv6 in containers via `docker-compose.yaml` sysctls in `x-demetra-app`
  (`net.ipv6.conf.all.disable_ipv6=1`, `net.ipv6.conf.default.disable_ipv6=1`).
  This is hygiene only — it does not fix the ECONNRESET. Requires `docker compose up -d`.
- Confirmed the MNT-276 retry is the correct resilience layer and should stay.

## Known follow-up (not fixed this session)

- Raise `MAX_AGENT_NETWORK_ATTEMPTS` (currently 5) and/or
  `AGENT_NETWORK_BACKOFF_BASE`, since server-side resets can cluster for minutes.
- Apply the IPv6 sysctls with `docker compose up -d` on the host.
- Optionally route DeepSeek through OpenRouter for a single, better-managed
  gateway instead of hitting `api.deepseek.com` directly.

---

## Follow-ups

- None beyond the "Known follow-up" items above.

## References

- Related: [[2026-11-03-mnt-276-econnreset-retry-for-agents]]
