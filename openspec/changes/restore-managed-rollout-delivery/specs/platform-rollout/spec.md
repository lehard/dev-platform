## ADDED Requirements

### Requirement: Blocked managed rollout is recoverable through the same delivery contract

A terminal blocked rollout attempt SHALL preserve enough structured evidence to identify the owning blocker when that blocker is deterministically knowable, and a later retry after the blocker is resolved SHALL reuse the normal exact-version reviewed-rollout path rather than require a manual alternate delivery mechanism.

#### Scenario: Multiple managed repositories fail for different reasons

- **WHEN** one platform release produces blocked rollout attempts in multiple managed repositories
- **THEN** each repository is classified from its own structured evidence
- **AND** the platform SHALL NOT infer one shared root cause merely from temporal coincidence

#### Scenario: Existing diagnostic reports unknown but a stable platform stage exposes the blocker

- **WHEN** rollout terminates in a platform-owned stage with enough bounded structured state to identify the failure class
- **THEN** the terminal diagnostic SHALL use that stable category/reason instead of `unknown`
- **AND** SHALL NOT scrape arbitrary unrestricted logs to guess a cause

#### Scenario: Failure is caused by shared-workspace permissions owned by another accepted change

- **GIVEN** the same root cause is already owned by managed change `enforce-shared-workspace-permissions`
- **WHEN** rollout repair diagnoses that condition
- **THEN** this change records the dependency instead of implementing a competing permission mechanism
- **AND** independent rollout defects continue to be repaired in parallel

#### Scenario: Blocker is resolved and rollout is retried

- **WHEN** the exact target release or a later cumulative immutable release containing the fix is retried
- **THEN** each managed repository passes normal rollout preparation and creates/reuses its reviewable rollout PR, or is proven already at the exact target version
- **AND** its failure-streak tracker is closed by the existing successful-preparation path rather than manual bookkeeping

### Requirement: Rollout recovery preserves conflict and ownership safety

Repairing a failed rollout SHALL NOT turn unresolved Copier conflicts, project-owned path ambiguity, changed automation head, failed validation or branch-protection requirements into success.

#### Scenario: Copier leaves an unresolved rejection during recovery

- **WHEN** a retry still contains a non-ignored `.rej` or unresolved ownership conflict
- **THEN** rollout remains blocked
- **AND** no downstream default-branch mutation or silent overwrite occurs

#### Scenario: Historical platform workflow differs only in redundant blank separators

- **GIVEN** a platform-owned `.github/workflows/dev-platform.yml` has no YAML block scalar content
- **AND** its committed historical rendering differs from its recorded immutable baseline only by repeated blank separators
- **WHEN** Copier reports a conflict for that workflow during guarded recovery
- **THEN** rollout MAY treat that formatting-only difference as baseline-equivalent and recopy the platform-owned workflow
- **AND** comments, non-empty content, all other paths, and workflows containing YAML block scalars SHALL remain byte-sensitive ownership checks
