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

## Upgrade

```bash
copier update --trust
```

Perform upgrades in a dedicated worktree and review the diff. If there is a merge conflict, resolve ownership rather than automatically preferring template or project content.

## One-time GitHub Actions sharing setting

`dev-platform` is private. In GitHub open **dev-platform -> Settings -> Actions -> General -> Access**, select **Accessible from repositories owned by `lehard` user**, and save. This allows other private repositories owned by the same account to call `.github/workflows/project-ci.yml`.
