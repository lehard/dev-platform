# Adoption guide

## New repository

```bash
copier copy --trust https://github.com/lehard/dev-platform.git ./new-project
cd ./new-project
python3 scripts/platform_doctor.py
```

Commit `.copier-answers.yml`; Copier uses it to calculate future template updates.

## Existing repository

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

The bootstrap deliberately does **not** run `openspec init` automatically when adopting into an existing Git repository, because current OpenSpec init can migrate/remove OpenSpec-managed legacy files. Review the existing tool files first, then run the printed `openspec init ...` command manually.

After the initial adoption is reviewed, the following generated defaults are treated as **project-owned** and preserved by later Copier updates: `AGENTS.md`, `README.md`, `dev-platform/checks.toml`, `openspec/config.yaml`, and `docs/engineering/project-rules.md`. Shared lifecycle scripts, shared workflow documentation and self-contained platform CI remain platform-managed.

If the project needs additional compatibility helpers to be mandatory, declare repository-relative paths in `.dev-platform.toml` as `project_required_files = ["..."]` rather than customizing `scripts/platform_doctor.py`.

## Upgrade

For an ordinary manual upgrade:

```bash
copier update --trust
```

Perform upgrades in a dedicated worktree and review the diff. If there is a merge conflict in a platform-managed file, resolve ownership rather than automatically preferring template or project content. Project-owned files listed above should remain unchanged by Copier after their initial creation.

Stable Copier renders synchronize `.dev-platform.toml` `platform_version` from `.copier-answers.yml` `_commit`; platform doctor treats disagreement between those records as blocking drift.

Once an adopted repository is intentionally promoted to `managed` in the central `managed-projects.json` registry, new stable platform releases are eligible for automatic exact-version Copier rollout PRs. The rollout system still stops at a PR; it does not auto-merge.

## CI access

Generated downstream CI has been self-contained since platform v1.0.1. A managed private project does **not** need GitHub Actions access to execute a reusable workflow from the private `dev-platform` repository. Platform CI changes arrive through reviewed Copier updates instead.

The only cross-repository credential required for central automated rollout is the dedicated least-privilege Dev Platform GitHub App described in `docs/managed-rollout.md`.
