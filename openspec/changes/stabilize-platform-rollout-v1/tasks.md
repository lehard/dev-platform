# Tasks

## 1. Copier/version stability

- [x] 1.1 Raise `_min_copier_version` to the tested `9.17.0`.
- [x] 1.2 Record Copier minimum/tested versions in generated project config.
- [x] 1.3 Make doctor diagnose incompatible installed Copier versions.

## 2. Upgrade safety

- [x] 2.1 Add unresolved `.rej` / Git conflict-marker blocking to platform doctor.
- [x] 2.2 Add unit coverage for clean, `.rej`, and inline-conflict states.
- [x] 2.3 Add Copier upgrade smoke preserving project-owned customizations.
- [x] 2.4 Run upgrade smoke for all three workflow profiles in CI.

## 3. Workflow immutability

- [x] 3.1 Pin central `actions/checkout`, `actions/setup-python`, and `actions/setup-node` uses to full commit SHAs.
- [x] 3.2 Add contract test preventing regression to mutable `actions/*@vN` refs.

## 4. Release lifecycle

- [x] 4.1 Replace branch-alias release documentation with SemVer Git-tag policy.
- [x] 4.2 Add guarded `VERSION`-driven tag/release workflow.
- [ ] 4.3 After stabilization merge, pin generated reusable CI to the stabilization commit SHA.
- [ ] 4.4 Add `VERSION=1.0.0`; confirm `v1.0.0` tag and GitHub Release are created at the release commit.

## 5. Verification

- [x] 5.1 Compile new/changed Python scripts.
- [x] 5.2 PR CI passes fresh render + upgrade smoke for `light`, `standard`, and `multi-agent`.
- [x] 5.3 Semantic completeness/correctness/coherence verification is recorded in `verification.md`; literal `/opsx:verify` remains a local OpenSpec workflow gate before archive.
