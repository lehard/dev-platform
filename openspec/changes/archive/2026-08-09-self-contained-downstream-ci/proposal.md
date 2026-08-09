# Proposal: self-contained downstream CI

## Why

First dogfood in private `planner-agent-lab` showed that a private reusable workflow fails before job creation unless repository-level Actions Access is enabled in `dev-platform`. This creates an unnecessary account-setting dependency for every rollout.

## Goals

- Make generated downstream CI self-contained in each Copier-managed project.
- Keep the same platform-managed `select_checks.py` contract and SHA-pinned GitHub Actions.
- Preserve reviewed platform propagation through `copier update`; no silent remote CI rewrite.
- Release as patch version `v1.0.1`.

## Non-goals

- Do not change project-specific quality pipelines.
- Do not remove `platform_ci_ref` yet; keep schema compatibility for v1 projects.
- Do not add a new CI framework or service.
