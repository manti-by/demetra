---
title: Docker image size optimization
generated: {by: demetra, at: '2026-11-23T00:00:00Z'}
description: mantiby/demetra:latest shrank from 1.01 GB to 708 MB by replacing a recursive chown that duplicated /opt/venv and the Rust toolchain with COPY --chown, slimming the C toolchain and switching to vim-tiny, keeping Rust, C and bun for target builds; the container suite passed 1556 tests.
type: investigation
status: stable
session_id: sess_6664750b-7e75-4d94-b0da-7cb892b4bbbc
services: [Dockerfile, docker-compose, docker-entrypoint]
branch: opencode/feature/optimize-docker-image-size
tickets: []
tags: [docker, infrastructure, image-size]
related: [2026-09-18-dockerfile-opencode-agents-skills.md, 2026-08-17-docker-setup-review.md, 2026-08-10-docker-compose-deploy.md, 2026-11-14-mnt-315-auto-deploy-on-master-commits.md]
---

# Docker image size optimization

## TL;DR

`mantiby/demetra:latest` went from 1.01 GB compressed to 708 MB: the recursive
`chown -R` that stored `/opt/venv` and the Rust toolchain twice is gone
(replaced by `COPY --chown`), `build-essential` became an explicit
`gcc g++ make libc6-dev pkg-config` set, and `vim` became `vim-tiny`. The Rust
toolchain, the C toolchain and bun stay because agents build target projects
inside the container, dev dependencies stay out of the runtime image, and
`make docker-test` (a throwaway `docker-compose.test.yaml`) passed 1556 tests.
The analysis below is the state before the change; the measured results are in
the 2026-11-23 16:45 update.

---

## Net effect

The biggest wins in the final stage, all still open, are:

- **Duplicated layers from `chown -R`.** The final `RUN ... chown -R demetra:demetra ... /opt/venv /usr/local/cargo /usr/local/rustup` rewrites every file it touches into a new layer, so the venv and the whole Rust toolchain are stored twice. `COPY --chown` removes the copy.
- **Rust toolchain** (`COPY --from=rust` of `/usr/local/cargo` and `/usr/local/rustup`). Nothing in `demetra/` references cargo or rustup, so it is only there for agents building target projects. It is probably the single largest item, but that is not measured yet.
- **`build-essential`** pulls in more than the C toolchain needed by native builds, for example `dpkg-dev` and its Perl dependencies.
- **`vim`** brings `vim-runtime`; `vim-tiny` is enough for interactive editing.
- **`ruff`** is a runtime dependency in `pyproject.toml`, so it ships in the venv. `demetra/workflows/lint.py` gates it behind `IS_RUFF_ENABLED`, so it has to stay.

## Current Dockerfile (master `e3b1648`)

**File:** `Dockerfile`

- The `builder` stage (`python:3.13.9-slim`) installs `gh` from the GitHub apt repo, pinned `opencode` (`OPENCODE_VERSION=2.2.5`), `wi` (`WI_VERSION=v0.2.1`), the static Docker CLI (`DOCKER_CLI_VERSION=27.3.1`), the compose plugin (`DOCKER_COMPOSE_VERSION=v2.29.7`), and runs `uv sync --frozen --no-dev --no-cache` into `/opt/venv`.
- `oven/bun:1` and `rust:1-slim` are used only as copy sources.
- The final stage (`python:3.13.9-slim`) installs `git vim gnupg openssh-client build-essential pkg-config`, copies every binary plus the venv and the Rust toolchain, then `chown -R`s the venv and toolchain.
- The `opencode --version` and `docker --version` / `docker compose version` asserts must survive any rewrite. They catch a stale cached `COPY --from=builder`.
- The local checkout was 37 commits behind `origin/master` when the session started. Upstream had added the Docker CLI/compose binaries, the deployer source copy to `/opt/demetra/src`, and `configs/derive-opencode-config.py`, so it was fast-forwarded before any analysis.

## Uncommitted edits on master (not from this session)

> **Consistency note (2026-11-24, Consistency Agent):** these edits are no longer
> uncommitted, and the "Current Dockerfile" section above describes the
> pre-change state. The edits below shipped and are the change measured in the
> 2026-11-23 16:45 update (708 MB, 1556 tests passing).

These edits appeared in the working tree on `master` between the analysis and this sync. They have not been built or tested:

- `build-essential` → `gcc g++ make libc6-dev pkg-config`.
- `vim` → `vim-tiny`, with a `/usr/local/bin/vim` symlink to `vim.tiny`.
- `useradd` moved above the `COPY` steps so `/opt/venv`, `/usr/local/cargo` and `/usr/local/rustup` can be copied with `--chown=demetra:demetra`.
- `/opt/venv`, `/usr/local/cargo` and `/usr/local/rustup` dropped from the later `chown -R`, which removes the duplicate layer.

## Open questions

- Is the Rust toolchain still needed in the image, or can it move to an opt-in build arg or a separate image variant for Rust target projects?
- Is bun used by agents at runtime? The React build runs in the separate `oven/bun:1` `react-build` compose service.
- How should tests run in-container? The runtime image is built with `--no-dev` and `.dockerignore` excludes `tests/`. Options are a `test` build target that adds the dev group and `tests/`, or bind-mounting the repo and running `uv sync --dev` at test time.

## Update — 2026-11-23 16:45

Decisions: the Rust toolchain, the C toolchain and bun stay, because agents build the target projects Demetra manages inside the container. This is now documented in `AGENTS.md`. Dev dependencies stay out of the runtime image and are installed only when the tests run.

- **Size:** compressed content went from 1.01 GB to 708 MB. Unpacked disk usage of the baseline image was 3.94 GB, inflated by the duplicate `chown -R` layer. Before the change, the unpacked filesystem was 1.9 GB: Rust toolchain 600M, `opencode` 242M, venv 229M, bun 88M, compose plugin 61M, `uv` 42M, `gh` 41M, `docker` 38M. `docker history` reports 0B per layer under the containerd snapshotter, so sizes were measured with `du` inside the container.
- **Tooling smoke test:** in the slim image, as user `demetra`, `opencode`, `wi`, `gh`, `bun`, `uv`, `cargo`/`rustc`, `gcc`/`g++`/`make`/`pkg-config`, `vim`, `git`, `gpg`, `ssh`, `docker` and `docker compose` all run. `cargo new && cargo build` and a `gcc` hello-world build and run. `/opt/venv`, cargo and rustup are owned by `demetra` and writable.
- **In-container tests:** the new `docker-compose.test.yaml` (project `demetra-test`) runs a tmpfs `postgres:18` and a `tests` service. That service bind-mounts the repo, runs `uv sync --frozen --group dev`, then `alembic upgrade head`, then `pytest tests/`. `make docker-test` runs it and always tears it down, returning pytest's exit code. Result: **1556 passed in 26.05s**, exit 0.
- **`UV_PROJECT_ENVIRONMENT=/opt/venv` is set only on the `tests` service, never in the image.** Agents run `uv sync` in target-project worktrees, and a global value would redirect their installs into Demetra's own venv. Without it, the bind-mounted repo's host `.venv` would be overwritten with a Linux venv.

---

## Follow-ups

- Commit on `opencode/feature/optimize-docker-image-size` and open a PR.

## References

- Related: [2026-09-18-dockerfile-opencode-agents-skills](/pages/2026-09-18-dockerfile-opencode-agents-skills.md), [2026-08-17-docker-setup-review](/pages/2026-08-17-docker-setup-review.md), [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md), [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
