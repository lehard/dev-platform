# Proposal: Validate release installation before publication

## Why

Current central CI renders profiles and smokes upgrades, but does not consistently apply rollout's installed-harness checks to those results. Several recent releases therefore failed only in real downstream rollout. A release candidate needs one bounded, repeatable installation contract before its immutable tag is created.

## What changes

- Add a repository-owned release installation validation entrypoint using real Copier copy and update results for a representative supported matrix.
- Apply the platform-owned rollout checks, including diff hygiene, doctor, reject and required-surface integrity checks, to rendered installations.
- Execute the same entrypoint in PR CI and in the publication job before tag creation.

## Success evidence

- Fresh and upgrade cases cover `harness_mode=platform` and `harness_mode=project` for GitHub; alternative SCM coverage matches documented support.
- Focused negative fixtures prove detection of whitespace, missing mandatory input, and unsynchronized capability surfaces.
- Validation runs no product/application commands and does not duplicate downstream rollout PR CI.

## Constraints

Keep the matrix representative rather than Cartesian. Reuse rollout-owned checks where possible. Do not modify product CI ownership.
