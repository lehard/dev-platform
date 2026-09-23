# platform-rollout Specification Delta

## ADDED Requirements

### Requirement: Rollout alerts reconcile against recovered project state

The platform SHALL offer a bounded reconciliation of open rollout failure issues against the managed project's authoritative current platform state. It SHALL close an existing issue with a resolution note only when recovery after its last failed release is proven. Unreadable or ambiguous evidence SHALL leave the alert open. The existing issue SHALL remain the sole durable alert record.

Reconciliation SHALL run periodically without requiring a later automated rollout or a manual stale-rollout supersession apply action.

#### Scenario: Project recovered outside rollout

- **GIVEN** an open rollout failure issue for a managed project
- **AND** the project's default branch has coherent platform version records proving recovery at or beyond the failed release
- **WHEN** alert reconciliation runs
- **THEN** it closes the existing issue with a recovery note

#### Scenario: Recovery cannot be proven

- **WHEN** the project version records are stale, inconsistent or unreadable
- **THEN** reconciliation leaves the issue open and reports why

#### Scenario: Reconciliation runs twice

- **WHEN** reconciliation repeats after an issue was closed
- **THEN** it makes no further mutation or duplicate alert record
