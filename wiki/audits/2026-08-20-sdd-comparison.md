---
title: SDD Methodology Comparison — Demetra vs BMAD vs GitHub Spec Kit vs OpenSpec
date: 2026-08-20
type: investigation
status: reference
session_id: manual-research
services: [workflows, agents, wiki]
branch: -
tickets: []
tags: [sdd, bmad, spec-kit, openspec, agentic, comparison, research]
related:
  - 2026-06-02-plan-loop-resolve-questions.md
  - 2026-08-05-post-build-validation.md
  - 2026-08-03-wiki-mcp-tools.md
---

# SDD Methodology Comparison — Demetra vs BMAD vs GitHub Spec Kit vs OpenSpec

## TL;DR

Demetra is a **runtime orchestrator** that *executes* SDD against external systems (Linear, OpenCode,
GitHub). BMAD, GitHub Spec Kit, and OpenSpec are **methodologies + toolkits** that *prescribe* the
spec-first shape of development inside a single repo. The three external SDD kits differ in how
"heavy" the ceremony is, whether specs are *fractured per-feature* (Spec Kit) or *consolidated as a
single living source of truth* (OpenSpec), or *staged through a multi-agent agile team* (BMAD).
Demetra already adopts pieces of all three (plan → build → validate → review loop, constitution in
`AGENTS.md`, persistent wiki as archival memory) but is missing the executable-spec layer that
makes BMAD/Spec Kit/OpenSpec guarantees — it treats the Linear ticket as the spec and the
OpenCode plan as the contract.

---

## 1. What is actually being compared

| Dimension | Demetra | BMAD v6 | GitHub Spec Kit | OpenSpec |
|---|---|---|---|---|
| **Primary artifact** | Runtime orchestrator (Python) | Methodology + prompt templates + workflow scripts | Toolkit (`specify` CLI) + Markdown templates | Methodology + CLI + Markdown schemas |
| **License** | (proprietary in this repo) | MIT (`bmad-code-org`) | MIT (`github/spec-kit`, 130k★) | MIT (`Fission-AI/OpenSpec`, 65k★) |
| **Repo layout** | `demetra/workflows/<step>.py` orchestrating CLI calls to OpenCode | `_bmad/` + `_bmad-output/` Markdown/YAML agent files | `specs/NNN-<branch>/` per-feature folder + `memory/constitution.md` | `openspec/changes/<name>/` + `openspec/specs/<capability>/` + `openspec/config.yaml` |
| **Spec granularity** | Per-Linear-ticket build plan (free-form Markdown, extracted by an LLM) | PRD + architecture + per-story file (`{epic}.{story}.md`) | Per-feature folder (`spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `contracts/`, `research.md`, `quickstart.md`) | Per-change delta + unified source-of-truth spec |
| **Spec lifecycle** | Created once per ticket, posted as a Linear comment, never re-archived | Created in chat, versioned as files, lives until replaced | Created per branch, merged to `main` via the PR, then archived | Change specs `propose → apply → archive`; archived specs are merged into the source-of-truth spec |
| **Agent model** | 6 named agents (`plan-agent`, `build-agent`, `resolve-agent`, `review-agent`, `validate-agent`, `merge-agent`) orchestrated imperatively in Python; agent prompts live in `.opencode/agents/*.md` | 6 personas (Analyst/Mary, PM/John, Architect/Winston, Developer/Amelia, UX/Sally, Tech Writer/Paige) invoked via slash commands in the IDE; each is a Markdown persona file | No first-class agents; the spec/plan/tasks commands are slash-command prompts that the *host* agent runs | Schema-driven slash commands (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`); agents are the *host*'s |
| **Human-in-the-loop** | Auto-mode posts plan questions as Linear comments and parks the ticket in `Awaiting Input`; review agents emit silent on success, build agent never commits/pushes | Analyst → PM → Architect → Dev chain with the human as validator at every handoff; per-story fresh chat | Review checkpoints at `/clarify`, `/analyze`, plan/tasks gates | Quick path (`/opsx:propose → /apply → /archive`) and step-by-step path with optional `/opsx:ff` fast-forward and `/opsx:sync` |
| **Backlog integration** | Native Linear watcher (`demetra/watcher.py`) polls TODO column | None — Linear/Asana/Jira handled by community forks | None — assumes tickets live in the repo as Markdown issues | Native `openspec-linearized` skill for Linear (and the pattern transfers to Asana/Jira) |
| **Long-term memory** | `wiki/` directory (72 pages today), Karpathy-pattern persistent session knowledge base; cross-linked, indexed, agent-writable via `wiki_search`/`wiki_get_page` MCP tools | `project-context.md` (auto-loaded into every workflow) + per-PRD/architecture/story Markdown under `docs/` | `memory/constitution.md` (9 articles) — immutable, versioned with dated amendments | Source-of-truth spec + archived changes; custom `spec-driven-with-adr` schema persists ADRs alongside specs |
| **Code as source of truth?** | **No** — code is generated; the Linear ticket + build plan + git branch are the contract | **No** — documents are source of truth, code is "temporal" (Brian Madison's framing) | **No** — specs generate code; the philosophy is explicit ("code serves specifications") | **No** — single living spec is the source of truth; the spec is continuously validated against the code |
| **Brownfield support** | Strong — operates against existing repos in worktrees | Medium — has a codebase flattener that emits `flattened-codebase.xml` for context; one-shot ingest rather than continuous | Weak — Spec Kit assumes greenfield or that you generate a spec from existing code via `/speckit.specify` | Strong — designed for incremental changes on legacy code; "explore" workflow with Repomix for brownfield context |

---

## 2. Demetra's current shape

Demetra is fundamentally a **dispatcher + session manager**, not a methodology. Its value is in the
runtime plumbing:

- **`main.py` (line 68–184)** — supervisor loop: `setup → plan → build → review → lint/test → PR →
  cleanup`, with typed exceptions (`InfiniteLoopError`, `UserCancelledError`, `AutoCancelledError`,
  `PullRequestError`, `ReviewError`, `BuildError`) routing the Linear ticket to `In Progress`,
  `Awaiting Input`, or back to `TODO`.
- **`demetra/workflows/` (12 step modules)** — each step is a Python orchestrator that shells out
  to an OpenCode agent, captures `(exit_code, stdout, stderr)`, and feeds the result forward.
- **`.opencode/agents/*.md` (6 agent prompts)** — `plan-agent`, `resolve-agent`, `build-agent`,
  `validate-agent`, `review-agent`, `merge-agent`. The plan agent uses terminal markers
  (`Ready to proceed to build.` / `Please check my questions above.`) as the **only** signal for the
  orchestrator to decide whether to continue ([plan.py:141](demetra/workflows/plan.py)).
- **`demetra/wiki/` (72 pages + INDEX.md + TEMPLATE.md + README.md + QUESTIONS.md)** — Karpathy's
  "LLM-maintained wiki" pattern. Every session produces a typed page (`debug | investigation |
  code-review | implementation`) with frontmatter, cross-links, and a follow-ups section. Surfaced
  to agents through `wiki_search`/`wiki_get_page`/`wiki_list_pages` MCP tools
  ([demetra/tools/wiki.py](demetra/tools/wiki.py)).
- **`AGENTS.md`** — single-file "constitution": architecture layering rules (`library → services →
  workflows → api → tools`), naming conventions, lint/type/test gate commands, git-flow branching
  with `<agent-name>/feature/<issue-id>-<slug>` convention.
- **Failure → Linear feedback loop** — `demetra/templates/{build_failed,pr_creation_failed,review_failed}.md`
  post structured comments on the ticket and move it to `Awaiting Input` so a human can intervene.

Demetra **does** carry a thin spec layer (the OpenCode plan), but the plan is **opaque**: it's a
free-form Markdown string emitted by the plan agent, extracted by an LLM
(`demetra/services/llm/openrouter.py:extract_plan`), posted as a Linear comment, and never
re-validated against the resulting code. The validate-agent ([[2026-08-05-post-build-validation]])
closes part of this loop — it diffs the staged changes against plan steps and feeds missing items
back as the next build task — but the plan itself has no formal schema and no durability past the
branch.

---

## 3. BMAD — "Build More Architect Dreams"

**Philosophy:** Spec-Driven Development + an agile team of specialized AI personas, with the
*documents* (PRD, architecture, per-story file) as the durable source of truth and the *code* as
the temporal output.

**Workflow (4 phases):**

1. **Analysis** (optional) — Analyst/Mary: brainstorm, market research, project brief, PRFAQ
   challenge.
2. **Planning** — PM/John: PRD, epics, user stories, acceptance criteria, implementation
   readiness gate. Architect/Winston: architecture document, API contracts, DB schemas, tech
   stack, implementation readiness review.
3. **Solutioning** — Detailed system architectures; cross-cutting concerns; integration patterns.
4. **Implementation** — Per-story loop: `bmad-create-story → bmad-dev-story → bmad-code-review →
   bmad-retrospective`. Each story runs in a **fresh chat** with the story file as the entire
   handoff context — this is how BMAD fights context loss.

**Artifact handoff chain:**

| Artifact | Carries | Handoff |
|---|---|---|
| Project Brief | Vision, scope, problem statement | Analyst → PM |
| PRD | Requirements, epics, stories, NFRs | PM → Architect |
| Architecture doc | Tech stack, APIs, schemas, patterns | Architect → Dev |
| Story file (`{epic}.{story}.{title}.md`) | Full implementation context for one unit | PM → Dev |
| `project-context.md` | Repo conventions, always loaded into every workflow | — |

**Tracks:** Quick Flow (bug-fix → tech-spec → dev-story), BMAD Method (full plan), Enterprise
(+ security/devops/test modules). v6 ships 12+ domain experts and modular expansion packs (Test
Architect/TEA, Game Dev Studio, Creative Intelligence Suite).

**Pros**

- **Multi-persona discipline.** Each step has a persona with a focused prompt; the LLM is not asked
  to be PM, architect, and dev simultaneously.
- **Document sharding works.** Story files are self-contained, which sidesteps the "context window
  fills with irrelevant information" failure that Demetra also fights (CONTEXT_COMPACTION_THRESHOLD
  in [[2026-07-23-session-tokens-audit-revalidation]]).
- **Per-story fresh chat is a real win.** Each story gets a clean context — Demetra's equivalent is
  the `MAX_BUILD_ATTEMPTS` budget but reuses the same session, which is why the build step
  sometimes drifts off-plan (see [[2026-08-19-build-agent-stale-session-deleted-worktree]]).
- **Agile vocabulary fits existing teams.** Sprint planning, retros, epics, stories — easy to sell
  inside a company that already runs agile.
- **Expansion packs** make it portable beyond software (game dev, CIS for innovation).

**Cons**

- **Heavy ceremony.** Four phases + per-story loop + code review + retrospective. Time-to-first-PR
  is documented as longer than the leaner kits.
- **Shared output dir.** `_bmad-output/` is the single landing zone; absolute paths in frontmatter
  break team/monorepo use (filed issue).
- **High token spend.** Creator-acknowledged on Tech Lead Journal podcast; Reddit thread on burning
  tokens with full flow is active.
- **No agent runtime.** BMAD is prompts + templates; coordination is on the human (slash-command
  handoffs). Demetra's orchestrator solves this gap by being a runtime.
- **Loose agent coordination.** Per Augment's research, agents "work in isolation with no central
  coordination point for the current feature" — the handoff is whatever the human typed into the
  PRD last.
- **IDE friction.** `/analyst`, `/pm`, `/dev` slash commands have known issues in Claude Code;
  community workarounds required.

---

## 4. GitHub Spec Kit — "Specifications as Executable Artifacts"

**Philosophy:** Spec-Driven Development as a **power inversion**: "specifications don't serve
code — code serves specifications." The PRD is the source that *generates* implementation. The
implementation plan is a precise definition that produces code. The gap between spec and
implementation is **eliminated**, not narrowed.

**Workflow (`/speckit.*` slash commands):**

1. **`/speckit.constitution`** — write `memory/constitution.md`, 9 immutable articles.
2. **`/speckit.specify`** — feature description → branch (`NNN-<slug>`) → `specs/NNN-<slug>/spec.md`
   with user stories, acceptance scenarios, and explicit `[NEEDS CLARIFICATION: ...]` markers for
   every ambiguity.
3. **`/speckit.clarify`** — resolve the NEEDS CLARIFICATION markers against the codebase (optional).
4. **`/speckit.plan`** — `plan.md` + `data-model.md` + `contracts/` + `research.md` + `quickstart.md`,
   enforced through Phase -1 gates (Simplicity, Anti-Abstraction, Integration-First).
5. **`/speckit.tasks`** — derived task list with `[P]` markers for parallelizable work.
6. **`/speckit.implement`** — execute tasks in order.
7. **`/speckit.analyze`** — cross-artifact consistency check.

**The constitution (9 articles):**

| # | Article | Enforces |
|---|---|---|
| I | Library-First | Every feature begins as a standalone library |
| II | CLI Interface Mandate | stdio/stdout, JSON, text in/out — observability |
| III | Test-First Imperative | No code before tests (TDD, red-first) |
| IV–VI | Project-Defined | Team fills in (security, integration, versioning, breaking changes) |
| VII | Simplicity | ≤3 projects for initial implementation, no future-proofing |
| VIII | Anti-Abstraction | Use framework features directly, single model representation |
| IX | Integration-First Testing | Real DBs/services, contract tests mandatory |

**Pros**

- **Templates are anti-LLM-drift prompts.** They force `NEEDS CLARIFICATION` markers, ban premature
  implementation details in `spec.md` (WHAT/WHY only), mandate test-first ordering, and run phase
  gates that the LLM cannot silently skip. This is exactly the kind of constraint Demetra's plan
  agent lacks.
- **GitHub-native and portable.** Works with Claude Code, Codex, Cursor, Copilot, Gemini CLI —
  any agent that can run shell. Installed via `uvx --from git+... specify init <PROJECT>`.
- **Constitution gives durable governance.** Dated amendments show evolution while principles stay
  immutable. Demetra's `AGENTS.md` plays the same role but is enforced by humans/Ruff rather than
  template phase gates.
- **Branch = spec folder.** A clean 1:1 mapping between feature branches and spec directories makes
  the PR review a spec-review.
- **Cross-artifact consistency check.** `/speckit.analyze` catches contradictions between
  `spec.md` / `plan.md` / `tasks.md` — Demetra has nothing equivalent.
- **130k★, official GitHub backing, 28k forks, MIT.** Strong ecosystem.

**Cons**

- **Waterfall feel.** The Jan Kowalik comment on Microsoft's blog post captures the criticism:
  "isn't it pushing us towards waterfall methodology a little?" Spec Kit's docs counter this with
  "specifications as living documents," but the per-feature folder ritual is heavyweight for small
  fixes.
- **Per-feature spec explosion.** Each feature gets its own folder; for a long-lived project with
  hundreds of features, navigation becomes the problem.
- **Constitution is rigid.** The 9 articles are opinionated; teams that don't agree with
  library-first or CLI-mandate will fight the templates.
- **No backlog integration.** Tickets live as Markdown issues in the repo; no first-class Linear /
  Jira connector (community extensions fill this).
- **Greenfield bias.** `/speckit.specify` works fine on brownfield but the templates don't surface
  existing-code context as well as OpenSpec's "explore" + Repomix pattern.
- **No runtime.** Spec Kit is prompt-and-template scaffolding; the agent that runs the slash
  commands is whoever you bring (Copilot, Claude Code, OpenCode, etc.).

---

## 5. OpenSpec — "Spec-Anchored Alignment"

**Philosophy:** A **single unified specification document** is the authoritative reference for the
system's design and capabilities. Changes are expressed as **delta specs** ("ADDED", "MODIFIED",
"REMOVED" sections) that merge into the source of truth during archive. The system stays
**continuously validated** against one living spec — "specs become living assets agents execute
against," not "documents agents read once."

**Workflow (Propose → Apply → Archive):**

```
Quick path:
  /opsx:propose <idea> → /opsx:apply [change-name] → /opsx:archive [change-name]

Step-by-step path:
  /opsx:new <change-name>
  /opsx:continue [change-name]   # repeat until planning artifacts complete
  /opsx:ff [change-name]         # optional fast-forward for remaining artifacts
  /opsx:apply [change-name]
  /opsx:sync [change-name]       # optional, before archive
  /opsx:archive [change-name]
```

**Artifacts (default `spec-driven` schema):**

| File | Purpose |
|---|---|
| `openspec/changes/<name>/proposal.md` | Intent, in-scope, out-of-scope, affected capabilities |
| `openspec/changes/<name>/tasks.md` | Numbered implementation checklist |
| `openspec/changes/<name>/specs/<capability>/spec.md` | Delta sections: `## ADDED Requirements`, `## MODIFIED Requirements`, `## REMIFIED Requirements`, `## REMOVED Requirements` |
| `openspec/changes/<name>/design.md` | Technical decisions |
| `openspec/specs/<capability>/spec.md` | **Source-of-truth spec** (always present, always current) |
| `openspec/archive/` | Archived change specs (audit trail) |

**Custom schemas:** `spec-driven` (default), `spec-driven-with-adr` (ADRs persist alongside specs),
`intent-driven`, `event-driven`, `minimalist`. Schema lives in `openspec/config.yaml`.

**Pros**

- **Single source of truth.** The whole-system spec lives in one place; feature interactions are
  visible because everything is co-located. Demetra's wiki has 72 separate pages — useful but
  fragmented.
- **Delta specs are diff-friendly.** `## ADDED Requirements` / `## MODIFIED Requirements` /
  `## REMOVED Requirements` sections make code review of specs as clear as code review of code.
- **Spec-as-source-of-truth validation.** Because the spec persists across changes, you can
  re-validate the system against the spec at any point. Spec Kit's per-feature folders don't give
  you this — you have to assemble the whole-system spec yourself.
- **Brownfield-first.** Designed for incremental changes to existing code. The "explore" workflow
  uses Repomix to compress a codebase for AI analysis before proposing the first change.
- **Parallel changes via Git WorkTrees + SubAgents.** OpenSpec documents a pattern where multiple
  changes propose on `main`, apply in isolated worktrees via SubAgents, then merge in order. Each
  SubAgent runs Verify before merge, keeping the source-of-truth consistent.
- **Linear MCP native.** `openspec-linearized` skill turns Linear issues into OpenSpec changes —
  exactly Demetra's Linear-watcher pattern, but with spec persistence on the other side.
- **ADRs as durable artifacts.** The `spec-driven-with-adr` schema keeps architectural reasoning
  alive past a single change. BMAD loses this when an epic closes.
- **Lower ceremony than BMAD.** Quick path is three slash commands.
- **65k★, MIT, npm package, actively maintained.**

**Cons**

- **Spec drift is on the team.** Per `specdriven.com`'s analysis, specs are plain Markdown with no
  built-in verification — they drift unless actively maintained. There's nothing in the format
  that alerts you when the spec no longer reflects the code.
- **No executability.** Specs are documentation artifacts, not verifiable contracts. You can't
  *run* a spec. Spec Kit's constitution + phase gates are stricter here.
- **Slash-command workflow assumes developer tooling.** Lower barrier than BMAD's multi-agent
  setup but still requires an AI coding assistant with command support.
- **No built-in runtime.** Like Spec Kit, OpenSpec is methodology + tooling — no orchestrator runs
  the loop end-to-end. Demetra fills this gap.
- **Single spec can get large.** For very large systems the source-of-truth spec becomes hard to
  navigate; you then start splitting by capability, which defeats the "single doc" philosophy.

---

## 6. Side-by-side: how each methodology maps to Demetra's existing pieces

| Demetra artifact | Equivalent in BMAD | Equivalent in Spec Kit | Equivalent in OpenSpec |
|---|---|---|---|
| `AGENTS.md` (architecture, naming, layering) | `project-context.md` + the 9 articles in BMAD-adopted projects | `memory/constitution.md` (9 articles, dated amendments) | `openspec/config.yaml` + a custom schema's rules block |
| Linear ticket (raw text → plan agent) | Analyst/Mary → PM/John → PRD | `/speckit.specify <feature>` → `spec.md` with NEEDS CLARIFICATION | `/opsx:propose` → `proposal.md` + delta spec sections |
| `plan-agent.md` + OpenCode `## Implementation Plan` | `bmad-create-story` output → `story file` | `/speckit.plan` → `plan.md` + `data-model.md` + `contracts/` | `/opsx:continue` → `design.md` + delta spec sections |
| `build-agent.md` (executes plan, no commit/push) | `bmad-dev-story` (fresh chat per story) | `/speckit.implement` (task-by-task) | `/opsx:apply` (executes against approved artifacts) |
| `validate-agent.md` (post-build plan coverage check) | `bmad-correct-course` (mid-flight re-plan) | `/speckit.analyze` (cross-artifact consistency) | `/opsx:ff` (fast-forward remaining artifacts) |
| `review-agent.md` (Cursor/CodeRabbit review) | `bmad-code-review` (slash command) | Manual (spec review at PR time) | Manual (delta-spec review at PR time) |
| `wiki/` (72 pages, cross-linked, indexed, agent-queryable) | `docs/` per-project + `project-context.md` | `specs/` folders + `memory/constitution.md` | `openspec/specs/` (source of truth) + `openspec/archive/` |
| `failure → Linear comment → Awaiting Input` | `bmad-correct-course` → human review of updated docs | `/speckit.clarify` (resolve ambiguities) | `/opsx:sync` (re-sync spec before archive) |
| `MAX_BUILD_ATTEMPTS` / `MAX_REVIEW_ATTEMPTS` budgets | Per-story retry within the dev-story loop | Re-run `/speckit.implement` | Per-task retry within `/opsx:apply` |
| Session step history (`plan`, `build`, `completed`, `failed`, `awaiting_input`) | `sprint-status.yaml` | Git branch + commit history | Change folder + `archive/` index |
| Worktree per Linear ticket | One worktree per epic (community pattern) | One branch per feature folder | One worktree per change (documented pattern) |

**Where Demetra is already stronger than any of the three kits:**

- **Runtime enforcement.** Demetra is the only one of the four that *runs* the loop. BMAD, Spec
  Kit, and OpenSpec all assume a human-in-the-loop drives the slash commands.
- **Failure routing.** Typed exceptions (`PullRequestError`, `ReviewError`, `BuildError`) route
  the ticket to `Awaiting Input` with structured Linear comments from
  `demetra/templates/{build_failed,pr_creation_failed,review_failed}.md`. Spec Kit and OpenSpec
  rely on the agent noticing failure and re-running.
- **Persistent session memory.** The wiki + MCP tools
  ([demetra/tools/wiki.py](demetra/tools/wiki.py)) give every agent access to past
  sessions. None of the three kits has this — the closest is BMAD's `project-context.md`, but
  it's loaded wholesale, not queryable by topic/ticket.
- **Multi-tool review.** Cursor + CodeRabbit are run in parallel with model-configurable review
  agents; the validate-agent gates plan coverage before review. None of the three kits have a
  dedicated plan-coverage gate.

**Where Demetra is weaker:**

- **Spec structure.** The plan is free-form Markdown extracted by `extract_plan()`. No
  `NEEDS CLARIFICATION` markers, no `## ADDED Requirements` deltas, no constitution gates.
  Drift is detected only by `validate-agent` post-hoc.
- **Cross-artifact consistency.** No equivalent of `/speckit.analyze` or OpenSpec's archive diff.
- **Long-term spec persistence.** When a branch merges, the plan lives only in the wiki (if
  written). There is no `openspec/specs/<capability>/spec.md` accumulating the system intent.
- **Per-story fresh chat.** Demetra reuses one OpenCode session across the whole workflow
  (`session_id` persists from plan → build → validate → review), which is why
  [[2026-07-23-session-tokens-audit-revalidation]] shows median `build` rows at ~15M tokens and
  CONTEXT_COMPACTION_THRESHOLD at 100k. BMAD's fresh-chat-per-story pattern would force
  re-architecting the build loop.
- **Brownfield context.** Demetra's wiki is built up over time, but there's no equivalent of
  OpenSpec's Repomix-driven "explore" workflow for ingesting an unfamiliar codebase.

---

## 7. Use-case fit

| Scenario | Best fit | Why |
|---|---|---|
| **Bug fix / 1-line change** | Demetra (auto mode) or Spec Kit Quick Flow | Lightweight ticket → plan → build → PR; no ceremony |
| **Greenfield new product, single team** | BMAD Method track | PRD + architecture + per-story discipline catches design issues early |
| **Greenfield new product, multi-team** | Spec Kit + Demetra runtime | Spec Kit's constitution + per-feature folders give governance; Demetra's runtime removes human-in-the-loop overhead |
| **Brownfield modernization, incremental** | OpenSpec + Demetra runtime | Delta specs + source-of-truth fit incremental changes; Demetra's wiki carries the history |
| **Compliance-heavy (finance, healthcare)** | BMAD Enterprise track (+ custom constitution articles) | Full governance suite, security/DevOps/test modules, audit trail in `_bmad-output/` |
| **Spec-as-contract (API-first)** | Spec Kit | Per-feature `contracts/` folder + test-first article; the constitution's library-first and CLI-mandate articles fit API design naturally |
| **Single-developer indie hack** | Demetra (auto mode) or OpenSpec quick path | Lowest ceremony, fastest time-to-PR |
| **Multi-developer team with backlog in Linear** | **Demetra + OpenSpec** (closest fit today) | Linear-watcher + auto-mode + wiki already exist; add `openspec-linearized` skill or a Demetra-native delta-spec step to persist specs |
| **Game development / creative work** | BMAD Game Dev Studio expansion pack | Domain-specific agents and workflows |
| **High-trust agent autonomy, low human review** | **Demetra** | Only Demetra has a runtime that pushes all the way to PR; the other three rely on slash-command handoffs |

---

## 8. Recommendations for Demetra (if the goal is to absorb SDD discipline)

These are exploratory — not action items. Each is grounded in the comparison above and the wiki
session history.

1. **Add a structured spec layer between the Linear ticket and the plan.** Adopt either
   OpenSpec's delta-spec format (`## ADDED Requirements` / `## MODIFIED Requirements` /
   `## REMOVED Requirements`) or Spec Kit's `spec.md` template. Either gives the build agent a
   machine-checkable contract. The plan-agent's free-form Markdown becomes a derived artifact,
   not the source of truth.

2. **Move from "one OpenCode session per workflow" to "fresh context per story/change."** This is
   BMAD's biggest win and would address the 15M-token median rows in
   [[2026-07-23-session-tokens-audit-revalidation]]. Demetra's
   `demetra/services/agents/opencode.py` already exposes `session_id` plumbing; the change is
   mostly in `run_plan_step` / `run_build_step` boundaries.

3. **Treat `AGENTS.md` as a `constitution.md` with dated amendments.** Add a "## Amendments"
   section so the rules' evolution is auditable (Spec Kit pattern). Today the file is rewritten
   on every major session without a history trail
   ([[2026-08-03-agents-md-and-wiki-consistency]]).

4. **Add a `/speckit.analyze`-equivalent cross-artifact check.** The validate-agent already
   compares the staged diff against the plan; extend it to also cross-check the plan against the
   original ticket text + `AGENTS.md` rules, and post any drift as a structured Linear comment.

5. **Persist the source-of-truth spec.** OpenSpec's `openspec/specs/<capability>/spec.md` gives the
   system a single living reference. Demetra's wiki has 72 fragmented pages; a per-capability
   spec folder (sibling to the wiki) would let agents answer "what does this system do today"
   in one query instead of grepping the wiki.

6. **Wire `openspec-linearized` (or write a Demetra equivalent).** The skill already exists for
   OpenSpec; Demetra's `demetra/watcher.py` polls Linear TODO → would become the bridge that
   turns each ticket into an OpenSpec change folder. The wiki becomes the archive.

7. **Don't replace the runtime.** None of the three kits has a runtime. Demetra's value is
   precisely the loop that BMAD/Spec Kit/OpenSpec leave to the human. The right move is to **layer
   a spec methodology on top of the runtime**, not to replace the runtime with one of the kits.

---

## Follow-ups

- None tracked. This is reference material; revisit if/when the team decides to layer a spec
  methodology on top of the Demetra runtime.

## References

- Demetra `main.py` supervisor loop — [main.py:68–184](main.py)
- Demetra plan workflow + agent prompts — [demetra/workflows/plan.py](demetra/workflows/plan.py), [.opencode/agents/plan-agent.md](.opencode/agents/plan-agent.md)
- Demetra wiki conventions — [wiki/README.md](wiki/README.md), [wiki/TEMPLATE.md](wiki/TEMPLATE.md)
- Demetra wiki MCP tools — [[2026-08-03-wiki-mcp-tools]]
- Demetra post-build validation — [[2026-08-05-post-build-validation]]
- Demetra plan-loop resolve pattern — [[2026-06-02-plan-loop-resolve-questions]]
- Demetra session token audit (median 15M tokens / build row) — [[2026-07-23-session-tokens-audit-revalidation]]
- Demetra build agent stale-session incident — [[2026-08-19-build-agent-stale-session-deleted-worktree]]
- Demetra `AGENTS.md` revalidation — [[2026-08-03-agents-md-and-wiki-consistency]]
- BMAD Method overview — https://github.com/bmad-code-org/BMAD-METHOD, https://docs.bmad-method.org/
- BMAD agents reference — https://docs.bmad-method.org/reference/agents
- BMAD v6 module list (BMM, BMB, TEA, BMGD, CIS) — https://github.com/bmad-code-org/BMAD-METHOD
- BMAD third-party analysis (agents "work in isolation with no central coordination point") — https://www.augmentcode.com/guides/bmad-method-ai-development
- BMAD spec-driven analysis (specs as source of truth, code as temporal) — https://recruit.group.gmo/engineer/jisedai/blog/the-bmad-method-a-framework-for-spec-oriented-ai-driven-development/
- BMAD vs Spec Kit vs OpenSpec comparison — https://redreamality.com/garden/notes/bmad-method-guide/
- GitHub Spec Kit repo + methodology — https://github.com/github/spec-kit, https://github.com/github/spec-kit/blob/main/spec-driven.md
- GitHub Spec Kit official docs — https://github.github.com/spec-kit/
- Spec Kit "Power Inversion" + 9 articles — https://github.com/github/spec-kit/blob/main/spec-driven.md
- Spec Kit quick start — https://github.github.com/spec-kit/quickstart.html
- Microsoft DevBlog on Spec Kit — https://developer.microsoft.com/blog/spec-driven-development-spec-kit
- OpenSpec repo — https://github.com/Fission-AI/OpenSpec
- OpenSpec overview — https://intent-driven.dev/knowledge/openspec/
- OpenSpec practical guide — https://www.todorovic.dev/blog/spec-driven-development-with-openspec-practical-guide
- OpenSpec with Linear MCP — https://intent-driven.dev/blog/2026/01/11/linear-mcp-openspec-sdd-workflow/
- OpenSpec with Git WorkTrees — https://intent-driven.dev/blog/2026/04/01/openspec-git-worktrees-opencode/
- OpenSpec spec-driven-with-ADR schema — https://intent-driven.dev/blog/2026/04/29/spec-driven-development-with-adr/
- OpenSpec capability analysis (no executability, low ceremony) — https://specdriven.com/landscape/openspec
- DeepLearning.AI SDD course outline — https://www.deeplearning.ai/courses/spec-driven-development-with-coding-agents
- SpecDriven 2026 guide — https://www.thebcms.com/blog/spec-driven-development
