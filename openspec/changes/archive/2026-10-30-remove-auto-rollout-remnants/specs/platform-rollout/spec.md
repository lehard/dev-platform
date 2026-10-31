## MODIFIED Requirements

### Requirement: Existing stale rollout debt can be reconciled without creating a release

The platform SHALL provide an explicit maintenance mode for reporting and reconciling stale eligible rollout PRs across the current managed registry using the same identity and SemVer rules as normal rollout. The maintenance (its dry-run plan and its apply) SHALL run only when an operator dispatches it; a scheduled run of the same workflow SHALL NOT plan or apply stale-rollout reconciliation.

#### Scenario: Maintenance runs in dry-run mode

- **WHEN** an operator/agent invokes stale-rollout maintenance without mutation
- **THEN** it reports the exact managed repository/PR/version decisions it would apply
- **AND** performs no cross-repository write

#### Scenario: Maintenance applies cleanup

- **WHEN** reviewed maintenance mutation is invoked
- **THEN** it closes only PRs proven stale by committed downstream version or a safely available newer rollout target
- **AND** never mutates candidate/excluded repositories

#### Scenario: No scheduled maintenance

- **WHEN** the maintenance workflow runs on its schedule
- **THEN** it neither plans nor applies stale-rollout reconciliation

## ADDED Requirements

### Requirement: Managed project-owned publication harnesses prove exact-head merge safety without platform rewrites

A managed repository with `harness_mode=project` SHALL retain ownership of its repository-specific task/worktree/integration harness, but that ownership SHALL NOT weaken the platform-owned merge-safety invariant. Managed rollout SHALL treat exact-head publication safety as a conformance requirement for project-owned publication code and SHALL NOT rewrite project-owned harness bytes to obtain it. A project-owned harness that does not prove conformance SHALL fail closed with an actionable diagnostic and SHALL be preserved rather than overwritten.

Advancing `.copier-answers.yml` or `.dev-platform.toml` platform version metadata alone SHALL NOT count as successful safety adoption for a project-owned harness whose publication surface is known to require conformance.

#### Scenario: Project-owned publication harness does not prove conformance

- **GIVEN** a managed `harness_mode=project` repository whose publication surface lacks the exact-head conformance signals
- **WHEN** rollout runs
- **THEN** rollout fails closed before publishing a downstream update that claims safety conformance
- **AND** the project-owned harness bytes remain unchanged
- **AND** the diagnostic identifies the publication-safety compatibility blocker without guessing a rewrite

#### Scenario: Platform-owned harness receives the same safety release

- **GIVEN** a managed repository uses `harness_mode=platform`
- **WHEN** rollout applies the safety release
- **THEN** normal Copier-managed lifecycle files receive the exact-head publication implementation
- **AND** no project-harness compatibility rewrite is attempted

#### Scenario: Candidate or excluded repository is known to the registry

- **GIVEN** a repository is not in `managed` state
- **WHEN** ordinary managed rollout runs for the safety release
- **THEN** the repository is not mutated
- **AND** it receives the corrected contract only through a later deliberate adoption path

### Requirement: Project-harness rollout proves terminal reconciliation conformance without platform rewrites

For a managed project-owned harness whose lifecycle requires terminal status projection (it ships `scripts/finish_task.py`), rollout SHALL not treat platform version metadata advancement as successful adoption unless the project's own publication surface proves exact merged-PR terminal reconciliation. Rollout SHALL NOT rewrite project-owned harness bytes to obtain it; a harness that does not prove it SHALL remain unchanged and block rollout.

#### Scenario: Project-owned finish surface lacks terminal reconciliation

- **GIVEN** a managed `harness_mode=project` repository with `scripts/finish_task.py` whose publication surface lacks the terminal-reconciliation conformance signals
- **WHEN** rollout runs
- **THEN** rollout fails before advancing version metadata or modifying harness bytes

## REMOVED Requirements

### Requirement: Managed project-owned publication harnesses conform to shared exact-head merge safety

**Reason**: Replaced by "Managed project-owned publication harnesses prove exact-head merge safety without platform rewrites", which drops the reviewed legacy-harness compatibility migration and its scenarios.
**Migration**: None; the conformance gate and its fail-closed diagnostic are unchanged.


### Requirement: Compatibility migration activates before a project harness CLI guard

**Reason**: The legacy-harness exact-head migration is removed: every registered project is at v1.6.0 or later and no operator configuration supplies the legacy fingerprints.
**Migration**: None; a project-owned harness without exact-head conformance fails rollout closed.

### Requirement: Reviewed legacy-merge-harness exact-head migration adapts its known regression surface

**Reason**: Removed with the legacy-harness exact-head migration.
**Migration**: None.

### Requirement: Project-harness rollout proves terminal reconciliation conformance

**Reason**: Replaced by "Project-harness rollout proves terminal reconciliation conformance without platform rewrites", which drops the reviewed legacy-publish-harness terminal migration.
**Migration**: None; the conformance gate keeps failing closed for a finish surface without terminal reconciliation.
