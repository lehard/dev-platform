# Proposal: Repair managed rollout after v1.4.31

## Why

Release `v1.4.31` exposed two platform-owned rollout defects. The task-intake migration intentionally changes a marked part of project-owned root `AGENTS.md`, but the guarded-recopy post-snapshot classifies that intended migration as unsafe drift. Separately, platform doctor applies a shared local-workspace permission invariant to a GitHub-hosted runner that cannot provide the relevant group/setgid topology. Both failures stop reviewed downstream delivery even when project-owned rules remain intact.

## What Changes

- Reconcile the task-intake migration with guarded-recopy snapshot semantics so the one deterministic marked insertion is accepted while all other project-owned changes remain fail-closed.
- Make shared-workspace permission enforcement aware of whether it is running in a supported shared local workspace or an ephemeral CI runner.
- Add regression coverage using representative Cuby/Jara agent-rule fixtures and GitHub Actions environment evidence.
- Publish a patch release and rerun the managed rollout from its immutable tag.

## Impact

- Affected capabilities: `managed-rollout`, `platform-doctor`.
- Affected surfaces: `scripts/rollout_project.py`, rendered `scripts/platform_doctor.py`, rollout/upgrade tests and operational rollout guidance if required.
- Project-owned lifecycle conflict resolution remains a downstream responsibility.
