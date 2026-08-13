# Proposal: Bound shared-workspace metadata to platform ownership

## Why

The shared-workspace safety contract currently has no sufficiently explicit boundary between platform-owned lifecycle metadata and arbitrary ignored machine-local tool state. That ambiguity can turn unrelated symlinks or concurrently written caches into false blockers for doctor and validation.

## What Changes

- Define an explicit ownership boundary for paths audited or repaired by shared-workspace tooling.
- Preserve permission enforcement for registered platform and Git metadata only.
- Make downstream group-write checks safely ignore foreign transient `.claude` caches while retaining checks for owned and tracked paths.
- Add regression coverage for external symlinks and concurrent foreign cache creation.

## Impact

- Affected specifications: `shared-workspace-safety` (new).
- Affected platform surfaces: shared workspace helper, rendered permission check wrapper, doctor and their tests.
- No application financial, product, deployment, or credential behavior changes.
