# Design: stabilize-platform-rollout-v1

## 1. Copier release boundary

Copier template versions use stable PEP-440-compatible Git tags (`v1.0.0`, `v1.1.0`, ...). A separate full commit SHA remains the execution pin for the reusable GitHub workflow.

A small `VERSION`-driven GitHub workflow creates a tag/release only when `VERSION` changes on `main`. It fails closed if the tag name already exists at another commit. Existing version tags are never moved.

The previously-created `release-v1.0.0` branch is not treated as a Copier release.

## 2. Upgrade-path CI

Platform CI keeps fresh-render validation for all workflow profiles and adds a Copier upgrade smoke for the same matrix.

For the initial stabilization change, the upgrade baseline falls back to the current pre-stabilization `main` commit. Once SemVer tags exist, the smoke test automatically selects the latest `v*` tag as its baseline.

The generated baseline project is committed, receives project-owned sentinel customizations, then runs `copier update --vcs-ref HEAD`. Validation asserts that project-owned content survives, no `.rej` remains, generated scripts compile, and the generated doctor passes.

## 3. Conflict guard

`platform_doctor.py` blocks two forms of unresolved update state:

- `*.rej` files outside ignored machine/dependency directories;
- Git's `leftover conflict marker` findings in working-tree or staged diffs.

The guard intentionally does not scan every committed file for marker-looking prose, reducing false positives in documentation.

## 4. Tool version stability

Copier `9.17.0` is both the minimum and platform-tested version for this rollout. CI installs exactly that version. The generated config records the minimum/tested pair and doctor warns on missing/newer versions while failing on an installed version below minimum.

OpenSpec version policy remains independent.

## 5. GitHub Actions supply-chain pinning

Central workflows replace `actions/*@vN` with the full commit SHA currently referenced by the trusted major tag. Human-readable comments retain the major version for maintenance.

The generated downstream workflow is already pinned to a full `dev-platform` commit SHA and remains unchanged in principle.

## Rollback

Before the first SemVer tag is published, rollback is a normal revert of this platform change. After a version tag is published, the tag is not moved; rollback requires a new patch release.
