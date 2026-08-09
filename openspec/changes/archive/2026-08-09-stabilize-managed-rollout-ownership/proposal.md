# Stabilize managed rollout ownership

## Why

The first live managed rollout to `lehard/planner-agent-lab` proved that GitHub App auth and fail-closed rollout work, but Copier correctly stopped on five downstream conflicts. Four of those files are project-owned by intent (`AGENTS.md`, `README.md`, `dev-platform/checks.toml`, `openspec/config.yaml`) yet are still treated as whole-file template-owned outputs. The rollout also revealed that `.copier-answers.yml` can advance to a new platform tag without mechanically guaranteeing that `.dev-platform.toml` records the same version.

## What changes

- Make explicitly project-owned files preserve existing downstream content during Copier updates while still being created for fresh projects.
- Keep shared platform behavior in managed scripts/docs rather than relying on overwriting project-owned files.
- Make platform bootstrap synchronize `.dev-platform.toml` `platform_version` from Copier `_commit` and make rollout validate that invariant.
- Allow project-specific required platform files to be declared as data in `.dev-platform.toml` instead of customizing `platform_doctor.py`.
- Update tests and rollout docs so future managed upgrades fail closed on version or ownership drift.

## Non-goals

- No automatic conflict resolution for arbitrary project code.
- No auto-merge of downstream rollout PRs.
- No first-time adoption automation.

## Definition of Done

- A rendered existing project can preserve the four project-owned files across an update.
- `platform_version` and Copier `_commit` cannot silently diverge after managed rollout.
- Planner Agent Lab can express its extra required helper without modifying shared doctor code.
- Platform CI and Copier upgrade smoke are green.
