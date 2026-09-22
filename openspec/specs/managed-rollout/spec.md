# managed-rollout Specification

## Purpose
Define the managed rollout registry, release ownership, and recovery controls for downstream adoption.

## Requirements

### Requirement: Guarded recopy permits only its deterministic task-intake migration

When managed rollout adds or normalizes the platform-owned marked task-intake reference in a project-owned root `AGENTS.md`, guarded Copier recopy SHALL accept that exact deterministic migration while continuing to reject any other change to protected project-owned paths.

#### Scenario: A mature downstream project receives the missing migration reference

- **GIVEN** a project-owned root `AGENTS.md` without the marked task-intake reference
- **WHEN** managed rollout performs guarded Copier recopy and its deterministic migration
- **THEN** rollout does not report project-owned drift solely for that marked insertion
- **AND** the project-owned rules remain otherwise unchanged

#### Scenario: Protected rules change outside the migration

- **GIVEN** a protected project-owned path changes beyond the deterministic migration
- **WHEN** guarded recopy comparison runs
- **THEN** rollout fails closed
- **AND** reports the affected protected path

### Requirement: Task-intake migration is idempotent

Managed rollout SHALL leave exactly one canonical marked task-intake reference after repeated successful runs and SHALL NOT duplicate or rewrite project-owned rule content.

#### Scenario: Project is rolled out twice

- **GIVEN** a project already has the canonical marked reference
- **WHEN** managed rollout is repeated
- **THEN** the reference remains singular
- **AND** guarded protected-path comparison still detects unrelated drift

### Requirement: Supersession reconciliation runs with its own operator-registry access in every job that calls it

Every workflow job that invokes `rollout_supersession.py reconcile` SHALL independently obtain read access to the operator-owned managed-project registry before calling it, since GitHub Actions job outputs do not carry a prior job's checked-out working tree across separate runners.

#### Scenario: A rollout or maintenance job runs on a separate runner from its planning job

- **GIVEN** a workflow's `plan` job checks out the private operator registry for its own matrix-building use
- **AND** a later job in the same workflow needs to call `rollout_supersession.py reconcile`
- **WHEN** that later job runs on its own fresh runner
- **THEN** it checks out the operator registry itself and passes `--registry` to the reconcile call

#### Scenario: Reconcile is invoked without a registry

- **WHEN** `rollout_supersession.py reconcile` is invoked without `--registry`
- **THEN** it fails closed with a missing-argument error rather than silently skipping the managed/base-branch safety check
