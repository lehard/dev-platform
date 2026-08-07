# dev-platform

`dev-platform` is the central, versioned developer platform for agent-first software projects. It provides a Project Factory, shared agent/OpenSpec rules, GitHub-aware lifecycle, validation and a deliberate learning loop without copying process files by hand.

## Core model

`doctor -> sync origin -> start -> OpenSpec -> implementation -> checks -> fetch origin again -> publish -> /opsx:verify -> archive`

The human user should not be a routine Git courier after an agent finishes implementation.

### Workflow profiles

- `light` — OpenSpec + checks + GitHub sync/publish for a single-agent project; no mandatory branch/worktree/board.
- `standard` — feature branches + GitHub sync/publish; default for most projects.
- `multi-agent` — standard + isolated worktrees + machine-local agent board and scope ownership.

Profiles are compositions of capabilities, not separate template forks.

### Publishing

- `pr` — safe default for `standard`/`multi-agent`: push feature branch and create PR with authenticated `gh`; no automatic merge.
- `direct` — explicit simplification: repeat fetch immediately before push and only fast-forward remote main; never force-push.

## OpenSpec policy

OpenSpec is the canonical planning layer for non-trivial changes. Current specs describe accepted behavior; active changes describe the approved delta. If implementation discovers a different goal, behavior, technical approach or task plan, update the relevant OpenSpec artifact before code diverges.

Non-trivial changes require project QA/tests **and** `/opsx:verify` before archive. The platform currently tests against OpenSpec 1.6.0 and records compatibility policy in generated `.dev-platform.toml`; it never silently upgrades a user's global CLI.

## Versioned downstream CI

Generated projects call reusable CI using the configured `platform_ci_ref`, never `@main`. The initial v1 line uses `release-v1.0.0`; release refs are append-only and must never move. Future upgrades change the ref only through reviewed Copier update PRs.

Because this repository is private, enable **Settings -> Actions -> General -> Access -> Accessible from repositories owned by `lehard`** before downstream private repositories call its reusable workflow.

## New project

Prerequisites: Git, Python 3.11+, Copier 9.x, OpenSpec CLI, and GitHub CLI (`gh`) when `publish_mode=pr`.

```bash
copier copy --trust https://github.com/lehard/dev-platform.git ./my-project
```

Copier asks for `workflow_profile`, `publish_mode`, and the versioned platform CI ref. `.copier-answers.yml` is committed so future platform updates can be reviewed with `copier update --trust`.

## Existing project

Adopt only from a clean dedicated branch/worktree and review every conflict. Existing repositories are never auto-migrated by OpenSpec bootstrap. Domain/project rules remain project-owned.

## Promotion loop

`project friction -> local classification -> deliberate sanitized promote -> dev-platform issue inbox -> OpenSpec platform change -> release -> reviewed Copier upgrade PRs`

Use `python3 scripts/agent_friction.py promote <event-id> --dry-run` before uploading a platform candidate.
