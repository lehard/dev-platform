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
- `direct` — explicit simplification: repeat fetch immediately before push and only fast-forward the configured main branch. Force push is forbidden.

## New project

Prerequisites: Git, Python 3.11+, Copier **9.17.0**, and preferably a platform-compatible OpenSpec CLI.

```bash
copier copy --trust https://github.com/lehard/dev-platform.git ./my-project
```

Copier uses stable Git version tags for template lifecycle. Once `v1.0.0` is published, normal project creation/update should use the latest stable tag unless an explicit `--vcs-ref` is supplied.

For existing repositories, adoption remains a reviewed migration: never blindly overwrite local agent/OpenSpec/process files.

## Update

From a clean project worktree:

```bash
copier check-update
copier update --trust
python3 scripts/platform_doctor.py
```

Always review the resulting diff. The doctor blocks unresolved `*.rej` files and Git/Copier conflict markers. Platform CI also tests upgrades from the last stable platform tag while preserving project-owned content.

## Release safety

Downstream reusable CI is pinned to an exact `dev-platform` commit SHA. Platform template versions use stable SemVer Git tags. See `docs/release-policy.md`.

GitHub Actions used by the central workflows are pinned to full commit SHAs rather than mutable major tags.

## Repository layout

- `copier.yml` — template questions and update contract.
- `template/` — files rendered into downstream projects.
- `.github/workflows/project-ci.yml` — reusable CI called by downstream projects.
- `.github/workflows/publish-version.yml` — creates SemVer tag/release when `VERSION` changes on `main`.
- `docs/` — platform ownership, adoption, releases and promotion-loop documentation.
- `openspec/` — OpenSpec configuration and changes for this platform itself.
- `tests/` — validation for new-project rendering, Git lifecycle and Copier upgrade behavior.

## Promotion loop

`project friction -> classify project/platform -> deliberate sanitized promotion -> OpenSpec change in dev-platform -> platform release -> reviewed downstream upgrade`

The next priority after rollout stabilization is real project adoption and observation, not adding more platform capabilities.
