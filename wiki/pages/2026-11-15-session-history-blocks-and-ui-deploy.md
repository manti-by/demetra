---
title: Collapsible session history blocks and a frontend-only deploy target
generated: {by: demetra, at: '2026-11-15T00:00:00Z'}
description: Records finishing a half-applied React `SessionHistory` change that made timeline blocks collapsible by default with name, cost and time headers, fixing undeclared `isOpen` state and a non-async test; it also added a `make deploy-ui` target rebuilding only the React bundle and reloading nginx, with 29 tests and tsc passing.
type: implementation
status: stable
session_id: ses_e1f6a316fffeH9qGy1hJrzbrI8
services: [SessionHistory, App.css, StyleGuide, Makefile, deployer]
branch: master
tickets: []
tags: [frontend, ui, session-history, deploy, makefile]
related: [2026-10-25-session-history-cost-and-failure-reasons.md, 2026-10-25-session-history-per-invocation-rows.md, 2026-11-14-mnt-315-auto-deploy-on-master-commits.md, 2026-11-24-mnt-321-external-providers-prices.md, 2026-11-25-mnt-323-worker-generation-swap.md]
---

# Collapsible session history blocks and a frontend-only deploy target

## TL;DR

Every block of the session-history timeline is now a collapsible card, collapsed
by default: the header shows the step name on the left and the cost and time on
the right, and opening a block shows the body as usual with the cost dropped
from the header (it is repeated in the token breakdown). The session started
with a half-applied working-tree change that did not compile — `isOpen` /
`setIsOpen` were used but never declared, and one test awaited inside a
non-async `it()` — so the work here was finishing that change rather than
starting it. Separately, `make deploy-ui` was added to the Makefile: it pulls,
rebuilds only the React bundle through the one-shot `react-build` compose
service and reloads nginx, leaving the image, the migrations and every running
container untouched, so a UI change ships without restarting the API or
interrupting the running workflows.

## Overview

Two independent pieces of work in one session.

**The history UI.** The request was: make all blocks collapsible and show, by
default, the name (left, as usual) plus the cost and time (right); when a block
is open, show the body as usual and hide the cost from the header. The
working tree already carried most of the implementation — the header turned
into a `<button>`, a chevron icon, a `data-open` attribute, a per-card
`mergeHistoryEntries` fold of step markers into their agent invocation rows, a
timing `dl` and pending/error card states — but it was left mid-edit and the
build was red.

**The deploy path.** `make deploy` rebuilds the `mantiby/demetra` image, runs
the migration one-shot and recreates `api worker watcher listener rq-dashboard
deployer`. That is a lot of motion for a CSS change: every recreation restarts
the API and the four workers, which can interrupt a running workflow. The
frontend, however, is not served by the API at all — nginx serves the built
bundle straight from disk, so a frontend change needs none of that.

## Step 1 — Finish the collapsible card

**File:** `react/src/components/SessionHistory.tsx:128-183`

The card component referenced `isOpen` and `setIsOpen` that were never
declared, so `tsc` refused the file and the component could not have rendered:

```
src/components/SessionHistory.tsx(151,18): error TS2552: Cannot find name 'isOpen'.
src/components/SessionHistory.tsx(156,24): error TS2304: Cannot find name 'setIsOpen'.
src/components/SessionHistory.tsx(1,16): error TS6133: 'useState' is declared but its value is never read.
```

The missing piece was the per-card state, collapsed by default:

```tsx
function SessionHistoryCard({ item }: SessionHistoryCardProps) {
  const { entry, start, status } = item;
  const [isOpen, setIsOpen] = useState(false);
```

The header is a real button so the card toggles with the keyboard, and the
cost only lives in the header while the block is collapsed:

```tsx
<button
  type="button"
  className="session-history-card-header"
  onClick={() => setIsOpen((open) => !open)}
  aria-expanded={isOpen}
>
  <span className="session-history-step">
    <ChevronIcon />
    {entry.step}
  </span>
  <span className="session-history-header-meta">
    {!isOpen && entry.cost != null && (
      <span className="session-history-cost">${entry.cost.toFixed(4)}</span>
    )}
    <time
      className="session-history-time"
      dateTime={entry.created_at}
      title={new Date(entry.created_at).toLocaleString()}
    >
      {formatTime(entry.created_at)}
    </time>
  </span>
</button>
{isOpen && ( /* failure message, status, timing, tokens, tools */ )}
```

Hiding the cost when the block is open is safe because the body repeats it: the
token `dl` renders a `Cost` row for the same `entry.cost`, and only
`kind='invocation'` / `kind='llm_call'` rows carry a cost at all — exactly the
rows whose token `dl` is rendered.

## Step 2 — Style the header

**File:** `react/src/App.css:1773-1815`

The header was a `<div>` and became a `<button>`, so it needed the button
reset (native border, background and font are removed) plus the two-column
layout — name on the left, cost and time on the right:

```css
.session-history-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.session-history-card[data-open="true"] .session-history-card-header {
  margin-bottom: 0.5rem;
}

.session-history-chevron {
  flex: none;
  margin-right: 0.35rem;
  transition: transform 0.15s ease;
}

.session-history-card-header[aria-expanded="true"] .session-history-chevron {
  transform: rotate(90deg);
}
```

`align-items: center` replaced `baseline` for the header row: the chevron is an
SVG whose baseline is its bottom edge, so a baseline-aligned flex row pushed it
a few pixels above the step name. The cost and the time keep their own
baseline alignment inside `.session-history-header-meta`, and that group is
`flex: none` so the cost and time never wrap.

## Step 3 — Tests and style guide

**File:** `react/src/components/SessionHistory.test.tsx:179`

One test awaited `expandAll()` inside a non-async `it()` — a leftover of the
collapse change that made `tsc` fail with `TS1308`:

```ts
it('hides token dl when all token fields are null', async () => {
```

The suite already covered the two states that matter:

- `renders collapsed cards with name, cost and time in the header` — the card
  starts `data-open="false"`, the header carries `$0.0500` and a `<time>`, and
  no token `dl` is rendered.
- `hides the header cost and shows the body when a card is expanded` — after a
  click the header cost is gone, the body token `dl` and its `Cost` row are
  there. The time in the header was asserted to stay.

**File:** `react/src/pages/StyleGuide.tsx:479-482`

The static history sample still used `<div class="session-history-card-header">`
markup, so it no longer matched the component. It now shows one collapsed card
(name + cost + time) and one expanded card (name + time, token breakdown).

## Step 4 — A frontend-only deploy target

**File:** `Makefile:38-48`

```make
# Frontend-only deploy: rebuild the React bundle and reload nginx. The image,
# the migrations and the long-running services are left alone, so a UI change
# ships without restarting the API or interrupting the running workflows.
deploy-ui:
	uv run python -m demetra.deploy_lock -- $(MAKE) deploy-ui-steps

deploy-ui-steps:
	git pull --ff-only
	docker compose --env-file .env.docker pull react-build || true
	docker compose --env-file .env.docker up --abort-on-container-failure react-build
	sudo service nginx reload
```

Why this is enough for a frontend change:

- **The bundle is built by a one-shot container, not by the app image.**
  **File:** `docker-compose.yaml:192-200` — `react-build` runs `oven/bun:1` with
  `./react` mounted and executes `bun install --frozen-lockfile && bun run
  build`, writing into the checkout's `react/dist`. No `mantiby/demetra` image
  build is involved, so the Python side is not rebuilt either.
- **nginx serves the bundle from disk.** **File:** `configs/nginx.conf:13-27,49-53`
  — `/assets/` is an alias on `<checkout>/react/dist/assets/` and `/` has
  `root <checkout>/react/dist`. The API never touches the frontend, so nothing
  has to be restarted for the new bundle to be served.
- **The long-running containers are never recreated.** `make deploy-steps` runs
  `up --detach --force-recreate ... api worker watcher listener rq-dashboard
  deployer`; `deploy-ui-steps` runs no `up` at all, so the API keeps its
  connections and the workers keep their running jobs.
- **The deploy lock is shared.** `deploy-ui` wraps the recipe in
  `demetra.deploy_lock` (`python -m demetra.deploy_lock -- ...`), the same Redis
  key (`demetra:deployer`) the daemon takes
  (`demetra/services/daemons/deploy_lock.py`). The daemon rebuilds the very
  same bundle in its `migrate react-build` step
  (`demetra/services/daemons/deployer.py:306`), so without the lock a manual UI
  deploy and the daemon could write `react/dist` at the same time.
- **A failed build does not go live.** `--abort-on-container-failure` makes the
  compose step exit non-zero, so make stops before the nginx reload and the
  previous bundle keeps being served.

`git pull --ff-only` behaves like in `make deploy`: it fast-forwards the
checkout and keeps uncommitted frontend edits as long as master does not touch
the same files, which is what makes "ship the UI fix I just made" possible.
`make deploy-ui-steps` skips the pull entirely when the checkout is already at
the right commit.

`AGENTS.md` gained the target in the Containerized Deploy section, next to
`make deploy`.

## Test Results

- `bun ./node_modules/vitest/vitest.mjs run src/components/SessionHistory.test.tsx` — 29 tests passed.
- `bun ./node_modules/typescript/bin/tsc --noEmit` — clean (it was red before this session).
- `bun ./node_modules/vite/bin/vite.js build --outDir /tmp/demetra-react-build` — built, 71 modules.
- Full suite: `bun ./node_modules/vitest/vitest.mjs run` — 186 passed, 2 failed. Both failures are in `src/pages/ChatPage.test.tsx` (`vi.mocked(getChat).mockResolvedValue is not a function`) and are pre-existing: the same two fail on a clean checkout (verified with `git stash`).
- `make -n deploy-ui-steps` — prints the recipe as expected. `make -n deploy-ui` also executes the recipe line, because GNU make runs lines containing `$(MAKE)` even in dry-run mode; that line then fails in this dev container, which has no docker binary at `DEPLOY["docker_path"]`.

Environment note: this container has no `node` binary, so the JavaScript
toolchain has to be driven through `bun` directly
(`bun ./node_modules/vitest/vitest.mjs run`, `bun ./node_modules/typescript/bin/tsc`).

## Follow-ups

- The **Total Tokens** and **Tool Usage** summary blocks are still always
  expanded. The request was read as covering the timeline blocks only — they
  have no name/cost/time header of their own — but they can be made
  collapsible the same way if that is wanted.
- `make deploy-ui` is a manual path only; the deploy daemon still deploys the
  whole stack on a master commit. A UI-only auto-deploy would need a daemon
  change (and a way to tell a frontend-only commit from a backend one).
- The bundle built inside the container is root-owned, so a host-side
  `bun run build` in the same checkout fails with `EACCES` on
  `react/dist/assets` (observed while verifying the build). Pre-existing wart
  of the containerised build, not introduced here.
- The working tree also carries an uncommitted change to
  `demetra/settings.py` (`DEPLOY["docker_path"]` → `/usr/bin/docker`) that
  predates this session and was left untouched.

## References

- Related: [2026-10-25-session-history-cost-and-failure-reasons](/pages/2026-10-25-session-history-cost-and-failure-reasons.md)
- Related: [2026-10-25-session-history-per-invocation-rows](/pages/2026-10-25-session-history-per-invocation-rows.md)
- Related: [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
- Related: [2026-11-24-mnt-321-external-providers-prices](/pages/2026-11-24-mnt-321-external-providers-prices.md)
- Related: [2026-11-25-mnt-323-worker-generation-swap](/pages/2026-11-25-mnt-323-worker-generation-swap.md)

> **Consistency note (2026-11-27, Consistency Agent):** Three items noted above have since settled: (1) `src/pages/ChatPage.test.tsx` was fixed and passes on `master`; (2) `DOCKER_PATH` stays `/usr/bin/docker` in `demetra/settings.py` while `docker-compose.yaml:71, 179` pins `/usr/local/bin/docker` for the containerised `deployer` and worker one-shots, and `Makefile` `deploy-steps` now swaps workers via `$(MAKE) worker-swap-steps` ([2026-11-25-mnt-323-worker-generation-swap](/pages/2026-11-25-mnt-323-worker-generation-swap.md)); (3) `entry.cost` on timeline headers now also populates for external providers and `kind='llm_call'` rows via [2026-11-24-mnt-321-external-providers-prices](/pages/2026-11-24-mnt-321-external-providers-prices.md).
