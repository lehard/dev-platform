# Proposal: Complete the public snapshot source boundary

## Why

The hardening delivered by Development Backlog #119 made public-distribution auditing, operator opt-in, and GitLab completion substantially safer. Post-merge review found two remaining cutover blockers.

First, the snapshot currently excludes all of `tests/` and `openspec/` while retaining README and GitHub CI surfaces that directly reference those paths. A fresh repository created from that snapshot would therefore not be a self-validating canonical source repository.

Second, `scripts/rollout_project.py` remains in the public candidate set while containing compatibility constants, messages, hashes, and migration branches tied to specific private downstream projects such as Jara_Fin, Planner Agent Lab, and Cuby. Those are operator/project compatibility details rather than generic product behavior.

The correction must preserve one public product core without hiding required source/test/spec material and without baking the current operator's private migration history into that product.

## What Changes

- Define the fresh public snapshot as a self-contained canonical source repository, not a reduced runtime export.
- Keep product tests and accepted OpenSpec specifications that are required by the repository's own CI, documentation, and verification contract.
- Permit explicit exclusion of maintenance/history-only material such as archived historical changes where that does not break repository invariants.
- Add snapshot smoke verification that operates on the extracted snapshot and proves required README/CI paths and public verification entrypoints are present and usable.
- Remove project-specific compatibility code/data from the public rollout implementation.
- Preserve any still-required private compatibility through an external operator-owned mechanism or a controlled migration path rather than a public hard-coded shim.
- Expand sanitization so project-specific compatibility markers cannot pass merely because they are not written as `owner/repo`.

## Impact

- Public distribution candidate policy, sanitizer, snapshot smoke tests, README/cutover documentation.
- Packaging of `tests/`, accepted `openspec/specs/`, and historical OpenSpec material.
- Generic managed-rollout implementation and its operator compatibility boundary.
- Existing GitLab/operator fixes from #119 remain unchanged except for regression coverage.
- Repository admin cutover and downstream project migrations remain outside this change.
