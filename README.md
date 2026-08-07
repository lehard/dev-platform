# dev-platform

`dev-platform` is the central, versioned developer platform for Alexey's agent-first software projects.

It extracts the reusable engineering workflow that matured in `Jara_Fin` and turns it into a project factory instead of copying process files by hand.

## What belongs here

Platform-owned concerns:

- repository-wide agent lifecycle (`AGENTS.md` contract);
- OpenSpec as the canonical planning layer for non-trivial product/architecture work;
- isolated Git worktrees for parallel agents;
- machine-local agent coordination board;
- safe merge-to-main flow;
- config-driven check selection;
- agent-friction recording and review;
- reusable GitHub CI;
- Copier template for new projects and future upgrades.

What does **not** belong here:

- product requirements;
- domain rules;
- finance-specific invariants from Jara_Fin;
- deployment credentials or machine-local access data;
- application architecture that is specific to one repository.

## New project

Prerequisites: Git, Python 3.11+, Copier 9.x, and preferably OpenSpec CLI.

```bash
copier copy --trust https://github.com/lehard/dev-platform.git ./my-project
```

The template asks for the project name, description, default branch and AI tools. Copier writes `.copier-answers.yml`, which is intentionally committed so the project can later receive platform upgrades.

The post-copy bootstrap initializes Git for a genuinely new destination, creates the machine-local `.claude/` coordination area, initializes OpenSpec for the selected tools only when the destination was not already a Git repository, and runs the platform doctor. Existing Git repositories are never auto-migrated by `openspec init`; the script prints the reviewed/manual command instead.

If OpenSpec is not installed on that machine, project creation still succeeds; `python3 scripts/platform_doctor.py` reports the missing prerequisite.

## Existing project

Adopt the platform in a dedicated branch/worktree:

```bash
copier copy --trust https://github.com/lehard/dev-platform.git .
```

Review every conflict. Existing product/domain rules stay project-owned; move them to `docs/engineering/project-rules.md` or module-level `AGENTS.md` files instead of mixing them into the platform-managed root contract.

## Updating a project

From a clean project worktree:

```bash
copier update --trust
```

Always review the generated diff and merge it through the normal project workflow. Platform upgrades are deliberately pull-requested/reviewed changes, not silent remote rewrites.

Because `dev-platform` is private, GitHub Actions sharing must be enabled once in this repository: **Settings -> Actions -> General -> Access -> Accessible from repositories owned by `lehard`**. Without that, downstream private repositories cannot call the reusable CI workflow.

## Repository layout

- `copier.yml` — template questions and update contract.
- `template/` — files rendered into downstream projects.
- `.github/workflows/project-ci.yml` — reusable CI called by downstream projects.
- `docs/` — platform ownership, adoption and promotion-loop documentation.
- `openspec/` — OpenSpec configuration and changes for this platform itself.
- `tests/` — validation for the project factory.

## Promotion loop

The intended lifecycle is:

`project friction -> classify project/platform -> OpenSpec change in dev-platform -> platform update -> reviewed upgrade PRs -> new projects inherit the improvement`

See `docs/promotion-loop.md`.
