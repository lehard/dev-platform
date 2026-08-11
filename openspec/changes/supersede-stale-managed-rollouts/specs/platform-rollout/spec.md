## ADDED Requirements

### Requirement: Older managed rollout pull requests are superseded deterministically

Managed rollout SHALL prevent accumulated older platform-update PRs from remaining actionable after a newer authoritative platform target is safely available or the downstream default branch has already advanced beyond them. Automatic supersession SHALL apply only to verifiably managed rollout PRs in repositories currently allowlisted as `managed`.

#### Scenario: Newer rollout PR is successfully prepared

- **GIVEN** managed repository R has open eligible rollout PRs for versions lower than target `vN`
- **WHEN** rollout successfully creates or reuses the validated eligible rollout PR for `vN`
- **THEN** the platform closes the lower-version eligible rollout PRs as superseded by `vN`
- **AND** records which newer target/PR superseded them
- **AND** does not force-push or merge any rollout PR

#### Scenario: Newer rollout preparation fails before replacement PR exists

- **GIVEN** an older eligible rollout PR remains open
- **WHEN** preparation of newer target `vN` fails before a validated `vN` PR exists
- **THEN** the platform leaves the older pending rollout PR open
- **AND** does not remove the last reviewable update path merely because a newer attempt failed

#### Scenario: Downstream default branch already advanced

- **GIVEN** the downstream default branch records platform version `vB`
- **AND** an open eligible rollout PR targets `vA` where `vA <= vB`
- **WHEN** rollout maintenance reconciles stale PR state
- **THEN** the PR is classified stale and may be closed as superseded by the already-adopted base state

#### Scenario: Open rollout PR targets a newer version than the current request

- **GIVEN** an eligible open rollout PR targets `vM`
- **AND** the current rollout request targets `vN` where `vM > vN`
- **WHEN** supersession logic evaluates the repository
- **THEN** it SHALL NOT close or mutate the newer `vM` PR
- **AND** the older `vN` request follows existing downgrade/stale fail-closed behavior

#### Scenario: PR resembles rollout by title only

- **WHEN** an open PR title/body resembles a platform update but its head/ownership/base contract does not prove it is a managed rollout PR
- **THEN** automatic supersession SHALL leave it untouched

### Requirement: Rollout PR identity is derived from reserved branch/version and trusted automation context

Automatic rollout cleanup SHALL identify eligible rollout PRs from the exact reserved branch form, stable SemVer target, configured base branch, and expected rollout automation context. Human-readable title text SHALL NOT be the sole identity signal.

#### Scenario: Candidate or excluded repository contains a rollout-like PR

- **GIVEN** a repository is not currently `managed` in `managed-projects.json`
- **WHEN** stale-rollout maintenance runs
- **THEN** the platform SHALL NOT mutate that repository or its PRs

#### Scenario: Unrelated dev-platform branch is open

- **WHEN** a PR head does not match exact `dev-platform/rollout-vMAJOR.MINOR.PATCH`
- **THEN** it is outside automatic rollout supersession

### Requirement: Superseded rollout branch cleanup is post-close and non-destructive

Remote branch deletion for a superseded rollout SHALL occur only after the corresponding PR is confirmed closed. Branch cleanup SHALL never use force-push and SHALL NOT redefine successful PR supersession as failure if only branch deletion fails.

#### Scenario: Superseded PR closes but remote branch deletion fails

- **WHEN** the stale rollout PR is confirmed closed
- **AND** remote rollout-branch deletion fails
- **THEN** the PR remains correctly superseded/closed
- **AND** the cleanup failure is surfaced as a warning with the exact repository/branch
- **AND** no unrelated branch is modified

### Requirement: Existing stale rollout debt can be reconciled without creating a release

The platform SHALL provide an explicit maintenance mode for reporting and reconciling stale eligible rollout PRs across the current managed registry using the same identity and SemVer rules as normal rollout.

#### Scenario: Maintenance runs in dry-run mode

- **WHEN** an operator/agent invokes stale-rollout maintenance without mutation
- **THEN** it reports the exact managed repository/PR/version decisions it would apply
- **AND** performs no cross-repository write

#### Scenario: Maintenance applies cleanup

- **WHEN** reviewed maintenance mutation is invoked
- **THEN** it closes only PRs proven stale by committed downstream version or a safely available newer rollout target
- **AND** never mutates candidate/excluded repositories
