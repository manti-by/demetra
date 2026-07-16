# demetra Wiki — Index

Session knowledge base for the demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Implementation: replan on missing build_plan (not step), validate Linear response payload, enable fallback session ID recovery (2026-07-16)
- [Empty build output and plan root causes](pages/2026-07-16-empty-build-output.md) — Debug: root causes of empty `build_plan` and stuck workflows; Linear null-response crashes at `graphql_request`, fallback session ID disabled (2026-07-16)
- [Empty Build Plan — Workflow Crashes After Worktree Creation](pages/2026-07-16-empty-build-plan-investigation.md) — Investigation: workflow exits after worktree creation, before plan agent runs (2026-07-16)
_Newest first._

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._
