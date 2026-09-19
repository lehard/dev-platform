# Proposal: Harden public distribution, operator isolation, and GitLab completion

## Why

The public-core split delivered by Development Backlog #118 established the right architecture, but post-merge review found several places where the implementation can report a stronger guarantee than it actually proves.

The public snapshot command currently packages a wider file set than its audit validates, the recorded audit does not inspect Git history, generic rendered guidance still assumes Development Backlog behavior without operator opt-in, operator environment state can leak into an otherwise portable project, and the GitLab adapter can return success for a non-green or unrelated pipeline.

These are release-boundary and lifecycle-correctness gaps. They block a clean public cutover and make the current external-client starter weaker than the accepted contract.

## What Changes

- Make the public-distribution audit and snapshot operate on the same exact candidate file set and block owner/project-specific material that the public boundary forbids.
- Add an explicit bounded history secret audit with truthful scope/limitations distinct from current-tree sanitization.
- Remove mandatory Development Backlog / Project-status / fleet/process-health instructions from a generic render unless operator integration is explicitly enabled.
- Make external operator state impossible to load into a portable project without an explicit project/operator opt-in.
- Unify operator config and managed-project registry discovery behind one documented contract and add a validation path for operator-owned configuration without committing live inventory.
- Make bounded GitLab delivery fail closed unless the published MR and CI evidence match the exact task HEAD and CI has reached the accepted green terminal state.
- Preserve human merge/acceptance as the GitLab pilot terminal handoff and preserve existing GitHub lifecycle safety.

## Impact

- `scripts/public_distribution.py`, public cutover docs, and tests.
- Project Factory generated guidance and operator-specific instruction surfaces.
- `template/scripts/_platform_common.py`, operator config loading, registry discovery, and operator validation.
- `template/scripts/gitlab_delivery.py` and its `finish_task.py` integration.
- Focused GitLab/operator/public-distribution tests plus full repository validation.
- No GitHub repository admin cutover, downstream migration, production deployment, or old-history rewrite is performed by this change.
