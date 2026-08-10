# Change: Preserve project-owned harness workflow documentation

## Why

The v1.4.11 rollout exposed an ownership bug for `harness_mode=project`: Copier still manages `docs/engineering/agent-workflow.md`, even though mature project-owned harnesses may intentionally maintain repository-specific publication and CI guidance there. Planner Agent Lab has such guidance, so rollout fails with a Copier conflict instead of preserving the project-owned lifecycle contract.

## What changes

- For `harness_mode=project`, preserve an existing `docs/engineering/agent-workflow.md` during Copier updates.
- Keep the generic workflow document platform-managed for `harness_mode=platform`.
- Add template-contract coverage so future rollouts do not regress this ownership boundary.

## Success criteria

A managed mature repository with `harness_mode=project` and customized workflow guidance can upgrade Dev Platform without Copier attempting to overwrite that file, while platform-owned harness projects still receive platform workflow documentation updates.