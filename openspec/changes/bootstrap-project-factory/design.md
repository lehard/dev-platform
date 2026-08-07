# Design

## Architecture

The platform has three layers:

1. **Factory layer** — Copier template and `.copier-answers.yml` for new-project generation and three-way updates.
2. **Shared runtime workflow** — dependency-light Python scripts copied into each project so agents can coordinate without requiring access to the central repository during normal work.
3. **Central CI layer** — a reusable GitHub Actions workflow; downstream repositories keep a tiny caller workflow.

## Ownership

Root `AGENTS.md` in generated projects contains platform process only. Project/domain rules live in the project-owned `docs/engineering/project-rules.md` or module-level rules.

The check-selection engine is platform-owned, while `dev-platform/checks.toml` is designed to be customized by each project.

OpenSpec is not vendored. `platform_bootstrap.py` initializes OpenSpec automatically only for a freshly created destination. When adopting the platform into an existing Git repository it prints the reviewed/manual `openspec init` command instead, because current OpenSpec initialization may migrate or remove OpenSpec-managed legacy files. Absence of the CLI is a doctor warning rather than destructive bootstrap failure.

## Update safety

Copier records template answers and performs updates as diffs/merges. The platform never directly rewrites downstream repositories remotely. Upgrades are expected to run in project worktrees and be reviewed before merge.

## CI

Downstream `.github/workflows/ci.yml` calls the central reusable workflow. The reusable workflow checks out the caller repository, prepares Python and Node runtimes, and delegates actual check selection to the versioned `scripts/select_checks.py` plus project-owned command configuration.

Until a stable release/tag policy is introduced, the bootstrap caller references `@main`; moving to immutable release refs is a follow-up before broad production rollout.

## Machine-local state

Agent board and friction logs live under ignored `.claude/`. They coordinate local concurrent agents without becoming a second backlog or leaking secrets into Git.
