# blocking-check-recovery Specification

## Purpose
Make every blocking platform check state whether a failure is a platform defect, a recoverable state with a recorded recovery step, or an intentional hard stop, so that no failure ends in an unexplained dead end and no recovery weakens a protected gate.

## Requirements

### Requirement: Blocking checks declare a failure class

Every blocking platform check that reports through the shared helper SHALL be cataloged with a failure class of platform defect, supported recovery or justified hard stop, and the catalog SHALL inventory at least the blocking checks named by the Requirement. A recoverable entry SHALL name a recorded recovery step; a hard-stop entry SHALL carry a written justification. A blocking check that reports through the helper without a catalog entry SHALL fail platform validation. A new or changed blocking check SHALL be added to the catalog and fail through the helper; this obligation is enforced by review, and the completeness of the inventory beyond the named checks is reported in the catalog and not asserted by validation.

#### Scenario: Uncataloged blocking check

- **GIVEN** a check blocks work through the shared helper with an id absent from the catalog
- **WHEN** it fires or platform validation runs
- **THEN** it fails explicitly naming the missing id.

### Requirement: Blocking failure messages distinguish the class

A blocking failure SHALL state whether it is a platform defect, a recoverable state with its recovery step, or an intentional hard stop, and SHALL NOT report the blocked check as passed or apply a default.

#### Scenario: Recoverable block

- **GIVEN** a legitimate state is blocked by a recoverable gate
- **WHEN** the check fails
- **THEN** the message names the recovery step
- **AND** following it, with its recorded decision, lets the work continue without disabling the gate.

### Requirement: Acceptance evidence covers rejection and recovery

Each cataloged gate SHALL have acceptance tests for rejection of the violating state and, for recoverable gates, for recovery from a legitimate state. The platform SHALL run them as part of validation.

#### Scenario: Missing recovery test

- **GIVEN** a recoverable catalog entry names no recovery test
- **WHEN** platform validation runs
- **THEN** it fails naming the gate.

### Requirement: Hotfix and recovery cannot weaken the protected surface

Neither a local hotfix nor any cataloged recovery SHALL disable independent review, protected publication, isolation of other agents' worktrees, credential restrictions, routing, provenance or evidence authenticity, Git-history protection or immutable releases. No universal force option or silent bypass SHALL exist.

#### Scenario: Attempt to disable a protected gate

- **WHEN** a hotfix record, recovery step or flag attempts to disable a protected gate
- **THEN** the attempt is refused with an explicit protected-surface message
- **AND** no check is recorded as passed.
