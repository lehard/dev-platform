# Adoption guide

## Primary interface: one-command onboarding

For a repository owned by the same GitHub account, the normal human action is now:

1. add the repository to the **Dev Platform Bot** GitHub App installation if repository access is restricted to selected repositories;
2. run **GitHub Actions -> Adopt Project -> Run workflow** in `lehard/dev-platform` and enter `owner/name`.

The workflow chooses the process. Do not choose Copier profile, harness mode, publish mode or OpenSpec bootstrap steps manually unless a project has an explicit exception.

The onboarding detector produces one of three states:

- `fresh` — no existing Dev Platform metadata or project process markers and the repository is small enough for the low-risk fast path;
- `existing` — the repository has its own agent/OpenSpec/CI process or enough existing code to require reviewed migration;
- `adopted` — Dev Platform metadata is already present.

### Fresh fast path

A fresh repository receives `standard` workflow, platform-owned harness and `direct` publish mode by default. Onboarding:

- renders the exact immutable Dev Platform release with Copier;
- performs safe non-interactive OpenSpec initialization with the expanded workflow set, including verify, without changing the developer's global OpenSpec profile;
- runs platform doctor, OpenSpec lifecycle hygiene, strict OpenSpec validation and selected project checks;
- creates an auditable adoption PR and automatically squash-merges it after those checks pass;
- promotes the repository to `managed` in the central registry.

This path is intended for new or nearly empty repositories. The detector is deliberately conservative: existing `AGENTS.md`, `CLAUDE.md`, `openspec/`, `.github/workflows/`, Dev Platform process files, or repository-size thresholds move the target to the cautious path.

### Existing-project cautious path

An existing repository uses the same **Adopt Project** workflow, but onboarding stops at a normal reviewable PR. Existing OpenSpec/tool files are not destructively initialized during the migration. Review project-specific agent rules, OpenSpec state, CI/check mappings and `.gitignore` before merge.

After the adoption PR is merged, run **Adopt Project** once more for the same repository. It detects the installed platform and performs only the central `managed` promotion. No second hand-written registry PR is required.

### Already adopted

If `.dev-platform.toml` or Copier ownership metadata already exists, onboarding does not recopy the project. It validates the explicit onboarding intent and promotes the repository to `managed` if necessary.

## Local developer readiness

After cloning an adopted project, the normal local preparation command is:

```bash
python3 scripts/dev.py ready
```

`ready` synchronizes the integration branch when it is safe to do so, restores/refreshes the configured OpenSpec integrations for Claude/Codex with the platform workflow set, and runs platform and agent doctors. OpenSpec-generated tool files remain machine-local/generated artifacts rather than platform-owned source.

Agents should prefer this entrypoint over asking the human to remember `project_sync`, OpenSpec init/update, `platform_doctor` and `agent_doctor` separately.

## Manual fallback

Direct Copier operation remains available for platform development, recovery and unusual migrations.

### New repository created locally

```bash
copier copy --trust https://github.com/lehard/dev-platform.git ./new-project
cd ./new-project
python3 scripts/dev.py ready
```

Commit `.copier-answers.yml`; Copier uses it to calculate future template updates.

### Existing repository

Adopt on a dedicated branch or worktree, never directly into a dirty integration branch.

```bash
copier copy --trust https://github.com/lehard/dev-platform.git .
```

Before accepting the result:

- preserve real project-specific agent rules;
- move domain rules out of the root platform contract;
- adapt `dev-platform/checks.toml` to the repository's actual test commands;
- inspect `.gitignore`;
- run `python3 scripts/platform_doctor.py`;
- run the selected/full project checks.

The manual existing-repository path deliberately does **not** auto-run a potentially destructive OpenSpec migration. After reviewing the adoption diff, `python3 scripts/dev.py ready` is the normal local integration refresh.

After the initial adoption is reviewed, the following generated defaults are treated as **project-owned** and preserved by later Copier updates: `AGENTS.md`, `README.md`, `dev-platform/checks.toml`, `openspec/config.yaml`, and `docs/engineering/project-rules.md`. Shared lifecycle scripts, shared workflow documentation and self-contained platform CI remain platform-managed.

If the project needs additional compatibility helpers to be mandatory, declare repository-relative paths in `.dev-platform.toml` as `project_required_files = ["..."]` rather than customizing `scripts/platform_doctor.py`.

## Upgrade

For an ordinary manual upgrade:

```bash
copier update --trust
```

Perform upgrades in a dedicated worktree and review the diff. If there is a merge conflict in a platform-managed file, resolve ownership rather than automatically preferring template or project content. Project-owned files listed above should remain unchanged by Copier after their initial creation.

Stable Copier renders synchronize `.dev-platform.toml` `platform_version` from `.copier-answers.yml` `_commit`; platform doctor treats disagreement between those records as blocking drift.

Once an adopted repository is `managed`, new stable platform releases are eligible for automatic exact-version Copier rollout PRs. The rollout system still stops at a PR; it does not auto-merge ordinary platform upgrades.

## CI access

Generated downstream CI is self-contained. A managed private project does **not** need GitHub Actions access to execute a reusable workflow from the private `dev-platform` repository. Platform CI changes arrive through reviewed Copier updates instead.

The only cross-repository credential required for onboarding and central automated rollout is the dedicated least-privilege Dev Platform GitHub App described in `docs/managed-rollout.md`.
