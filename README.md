# dev-platform

`dev-platform` is the central, versioned developer platform for agent-first software projects. It provides a Project Factory, shared agent/OpenSpec rules, GitHub-aware lifecycle, validation and a deliberate learning loop without copying process files by hand.

## Core model

`doctor -> sync origin -> start -> OpenSpec -> implementation -> checks -> /opsx:verify -> archive -> fetch origin again -> publish`

The human user should not be a routine Git courier or the person who remembers lifecycle cleanup after an agent finishes implementation.

A non-trivial OpenSpec change is not complete while its fully checked task list is still active. Agents record successful semantic verification in `verification.md` with `OpenSpec-Verify: PASS`, archive through the platform lifecycle helper, commit the resulting specs/archive state, and only then publish. Generated `finish_task.py` and CI enforce the completed-but-active hygiene rule.

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

Copier uses stable Git version tags for template lifecycle. Normal project creation/update uses stable tags unless an explicit `--vcs-ref` is supplied.

For existing repositories, adoption remains a reviewed migration: never blindly overwrite local agent/OpenSpec/process files.

## Update and managed rollout

A manual project update remains available from a clean worktree:

```bash
copier check-update
copier update --trust
python3 scripts/platform_doctor.py
```

`managed-projects.json` is the explicit project inventory and rollout allowlist. A successful stable platform release dispatches `.github/workflows/rollout.yml`, which performs an exact-version Copier update for `managed` entries, runs project validation, pushes a deterministic automation branch and opens a downstream PR. It does **not** auto-merge.

Registry states are deliberate:

- `managed` — adopted and eligible for rollout;
- `candidate` — active project awaiting reviewed adoption;
- `excluded` — known repository intentionally outside Dev Platform adoption/rollout, with an explanation.

Only `managed` can be mutated by rollout. `candidate` and `excluded` are non-mutating states, so repositories are not silently forgotten merely because they are not yet platform-managed.

Cross-repository access uses a dedicated least-privilege GitHub App, not the source repository `GITHUB_TOKEN` or a shared PAT. Each job uses a read-only source token for private `dev-platform` and a separate target token for downstream Contents/Pull-request/Workflow writes. See `docs/managed-rollout.md` for one-time setup and recovery.

Always review rollout diffs. The doctor blocks unresolved `*.rej` files and Git/Copier conflict markers. Platform CI also tests upgrades from the last stable platform tag while preserving project-owned content.

## Release safety

Downstream platform-managed CI is self-contained in each generated repository and changes through reviewed Copier updates. Platform template versions use stable SemVer Git tags. See `docs/release-policy.md`.

GitHub Actions used by the central and generated workflows are pinned to full commit SHAs rather than mutable major tags.

## Repository layout

- `copier.yml` — template questions and update contract.
- `template/` — files rendered into downstream projects.
- `managed-projects.json` — explicit downstream project inventory and rollout allowlist.
- `scripts/managed_projects.py` — registry validation and rollout matrix generation.
- `scripts/rollout_project.py` — exact-version downstream Copier rollout preparation.
- `.github/workflows/project-ci.yml` — legacy central workflow compatibility where retained; generated projects use self-contained CI.
- `.github/workflows/publish-version.yml` — creates SemVer tag/release when `VERSION` changes on `main`, then dispatches managed rollout.
- `.github/workflows/rollout.yml` — creates reviewed exact-version update PRs for managed repositories.
- `docs/` — platform ownership, adoption, releases, managed rollout and promotion-loop documentation.
- `openspec/` — accepted platform specs, active changes and archive for this platform itself.
- `tests/` — validation for new-project rendering, Git lifecycle, managed rollout and Copier upgrade behavior.

## Promotion loop

`project friction -> classify project/platform -> deliberate sanitized promotion -> OpenSpec change in dev-platform -> platform release -> reviewed downstream upgrade`

First-time adoption and recurring rollout are deliberately separate: adoption is a project-specific reviewed migration; rollout becomes automated only after a project is explicitly marked `managed`.
