# dev-platform

`dev-platform` is the central, versioned developer platform for agent-first software projects. It provides a Project Factory, shared agent/OpenSpec rules, GitHub-aware lifecycle, validation and a deliberate learning loop without copying process files by hand.

## Core model

`ready -> start -> OpenSpec -> implementation -> checks -> /opsx:verify -> archive -> publish`

The human user should not be a routine Git courier or the person who remembers lifecycle cleanup, OpenSpec setup or platform bootstrap steps.

A non-trivial OpenSpec change is not complete while its fully checked task list is still active. Agents record successful semantic verification in `verification.md` with `OpenSpec-Verify: PASS`, archive through the platform lifecycle helper, commit the resulting specs/archive state, and only then publish. Generated `finish_task.py` and CI enforce the completed-but-active hygiene rule.

### Workflow profiles

- `light` — OpenSpec + checks + GitHub sync/publish for a single-agent project; no mandatory branch/worktree/board.
- `standard` — feature branches + GitHub sync/publish; default for most projects.
- `multi-agent` — standard + isolated worktrees + machine-local agent board and scope ownership.

Profiles are compositions of capabilities, not separate template forks. `workflow_profile` describes the capabilities a repository uses; `harness_mode` independently records whether those lifecycle mechanics are implemented by Dev Platform (`platform`) or by a proven repository-specific harness (`project`). A mature multi-agent repository can therefore be `multi-agent + project` without being rewritten to the platform's board/worktree implementation.

### Publishing

- `pr` — safe default for reviewed/mature work: push feature branch and create PR; no automatic merge.
- `direct` — explicit simplification for intentionally simple repos: repeat fetch immediately before push and only fast-forward the configured main branch. Force push is forbidden.

## One-command project onboarding

The primary human interface is **GitHub Actions -> Adopt Project** with one required input: `owner/name`.

The platform detects the repository state automatically:

- `fresh` — new/nearly empty: apply the stable template, initialize full OpenSpec integrations, validate, auto-merge the auditable adoption PR, and promote the project to `managed`;
- `existing` — process-bearing or otherwise non-trivial: derive a conservative migration plan, prepare a reviewed migration PR and stop; after merge, rerun the same workflow to promote it to `managed`;
- `adopted` — platform metadata is already present: skip recopy and perform the managed promotion if needed.

For an existing repository, repository state and lifecycle ownership are separate decisions. If deterministic lifecycle markers show a coherent repository-owned harness (for example project check selection plus merge/publish mechanics, or a mature board/worktree surface), onboarding selects `harness_mode=project` and preserves those files. Worktree isolation plus agent/scope coordination selects `workflow_profile=multi-agent`. The calculated plan and its evidence are written into the adoption result, PR and workflow summary. Ambiguous collisions fail closed before Copier mutation rather than being silently overwritten.

With `harness_mode=project`, Dev Platform CI owns only platform/OpenSpec hygiene; the repository's existing dependency-aware CI remains authoritative for product/application checks. The platform does not require a project-owned `select_checks.py` to implement platform-only `--execute` or `--full` flags and does not install arbitrary product dependencies during generic onboarding.

The only normal manual security gate is adding the target repository to the Dev Platform GitHub App installation when the App is restricted to selected repositories. See `docs/adoption.md`.

For a local clone of an adopted project, use:

```bash
python3 scripts/dev.py ready
```

This safely synchronizes the integration branch when applicable, refreshes the configured OpenSpec integrations with the platform workflow set, and runs platform/agent doctors. In `harness_mode=project`, repository-owned lifecycle entrypoints remain authoritative.

Direct Copier commands remain documented as a recovery/advanced fallback, not the normal onboarding UX.

## Update and managed rollout

A manual project update remains available from a clean worktree:

```bash
copier check-update
copier update --trust
python3 scripts/platform_doctor.py
```

`managed-projects.json` is the explicit project inventory and rollout allowlist. A successful stable platform release dispatches `.github/workflows/rollout.yml`, which performs an exact-version Copier update for `managed` entries, runs project validation, pushes a deterministic automation branch and opens a downstream PR. Ordinary platform upgrades do **not** auto-merge.

## CI cost contract

Platform verification remains required locally before publication. Generated Dev Platform CI provides one automatic clean-environment validation path for the repository's publish mode (`pull_request` for PR publishing, `main` push for direct publishing), plus manual dispatch; superseded validation runs are cancelled. Platform publication and managed rollout remain separate side-effect workflows and are never made cancel-in-progress.

Registry states are deliberate:

- `managed` — adopted and eligible for rollout;
- `candidate` — active project awaiting adoption;
- `excluded` — known repository intentionally outside Dev Platform adoption/rollout, with an explanation.

Only `managed` can be mutated by ordinary rollout. Explicit one-command adoption may intentionally reclassify a candidate/excluded repository when the human starts onboarding it.

Cross-repository access uses a dedicated least-privilege GitHub App, not the source repository `GITHUB_TOKEN` or a shared PAT. See `docs/managed-rollout.md`.

## Release safety

Downstream platform-managed CI is self-contained in each generated repository and changes through reviewed Copier updates. Platform template versions use stable SemVer Git tags. See `docs/release-policy.md`.

GitHub Actions used by the central and generated workflows are pinned to full commit SHAs rather than mutable major tags.

## Repository layout

- `copier.yml` — template questions and update contract.
- `template/` — files rendered into downstream projects.
- `managed-projects.json` — explicit downstream project inventory and rollout allowlist.
- `scripts/adopt_project.py` — first-time repository classification plus mature-harness-aware adoption planning/preparation.
- `scripts/managed_projects.py` — registry validation, explicit promotion and rollout matrix generation.
- `scripts/rollout_project.py` — exact-version downstream Copier rollout preparation.
- `.github/workflows/adopt-project.yml` — one-command first-time onboarding orchestration.
- `.github/workflows/publish-version.yml` — creates SemVer tag/release when `VERSION` changes on `main`, then dispatches managed rollout.
- `.github/workflows/rollout.yml` — creates reviewed exact-version update PRs for managed repositories.
- `docs/` — platform ownership, adoption, releases, managed rollout and promotion-loop documentation.
- `openspec/` — accepted platform specs, active changes and archive for this platform itself.
- `tests/` — validation for project creation/adoption, Git lifecycle, managed rollout and Copier upgrade behavior.

## Promotion loop

`project friction -> classify project/platform -> deliberate sanitized promotion -> OpenSpec change in dev-platform -> platform release -> reviewed downstream upgrade`

First-time onboarding is automated where risk is low; recurring upgrades remain reviewed by default.
