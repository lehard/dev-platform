# Simplify project onboarding

## Why

First-time adoption currently exposes internal platform mechanics to the human even for nearly empty repositories: Copier choices, OpenSpec bootstrap, separate project and registry PRs, and multiple local readiness commands. The Cuby adoption demonstrated that these steps add ceremony without meaningful risk reduction for fresh repositories.

## What changes

- Add one GitHub Actions onboarding operation for `owner/name`.
- Detect `fresh`, `existing`, and `adopted` repository states automatically.
- Give fresh repositories a validated auto-merge fast path and automatic managed promotion.
- Preserve a reviewed migration PR for existing repositories.
- Add `python3 scripts/dev.py ready` as the single local readiness entrypoint.
- Make full OpenSpec workflow generation deterministic without changing user-global OpenSpec profile.
- Fix the generated OpenSpec YAML quoting issue and Codex verify path detection uncovered during Cuby adoption.

## Scope

Affects new-project/fresh adoption and first-time adoption of existing repositories. Ordinary managed release rollout remains reviewed and does not auto-merge.
