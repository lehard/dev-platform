# managed-rollout Specification Delta

## ADDED Requirements

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
