# managed-rollout Specification Delta

## ADDED Requirements

### Requirement: The managed registry is never stored in the public platform repository

The public Dev Platform repository SHALL NOT itself hold the managed-projects registry. Every workflow that reads or writes it SHALL resolve it from a generically-configured private operator repository instead, named only through a non-secret repository variable, never hardcoded in workflow or Python source.

#### Scenario: Operator repository is not configured

- **WHEN** a rollout-related workflow (`Adopt Project`, `Roll Out Platform`, `Reconcile Stale Managed Rollouts`) runs without the operator repository variable set
- **THEN** it fails closed with an explicit message before attempting any registry read or write

#### Scenario: Adopt Project promotes a repository to managed

- **WHEN** a repository completes adoption and is promoted to `managed`
- **THEN** the registry mutation is committed only into the private operator repository
- **AND** no commit is made to the public Dev Platform repository's own history

#### Scenario: Rollout or reconciliation plans against the registry

- **WHEN** `Roll Out Platform` or `Reconcile Stale Managed Rollouts` builds its matrix
- **THEN** it reads `managed-projects.json` only from a checkout of the configured private operator repository, authenticated with a token scoped to that repository alone
