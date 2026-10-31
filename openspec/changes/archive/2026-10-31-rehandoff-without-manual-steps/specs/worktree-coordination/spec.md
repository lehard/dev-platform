## ADDED Requirements

### Requirement: Admission keeps a handed-off developer claim

On admission the developer's board claim SHALL be kept as a handed-off record with its identity, overlap acknowledgments, handed-off head and PR, and SHALL claim no scope. Preflight SHALL write nothing and accept it as this worktree's claim only while that PR awaits a developer re-handoff and HEAD descends from the handed-off head; otherwise it SHALL refuse naming the command.

#### Scenario: Re-handoff after repair

- **GIVEN** a handed-off claim whose PR is repair-pending
- **WHEN** selected checks run in the same worktree on a descendant head
- **THEN** the scope gate accepts the claim with its acknowledgments and writes nothing

#### Scenario: Handed-off claim outside a re-handoff

- **WHEN** the PR is not awaiting a re-handoff or HEAD does not descend from the handed-off head
- **THEN** the scope gate refuses naming the state and the command

### Requirement: Only the re-handoff entry reactivates a handed-off claim

Only the developer re-handoff entry (`finish`, also through `execute_requirement.py advance`) SHALL reactivate a handed-off claim, after its preflight passed and before publication; its admission SHALL hand it off again at the new head. A new hard overlap SHALL still stop the re-handoff.

#### Scenario: Re-handoff publishes

- **WHEN** finish re-hands off a candidate
- **THEN** the claim is active during publication and handed off again at the new head after admission
