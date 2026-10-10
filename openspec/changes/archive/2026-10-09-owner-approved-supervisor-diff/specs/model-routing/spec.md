## ADDED Requirements

### Requirement: An owner-approved supervisor-written diff can be retained explicitly

The platform SHALL provide one explicit routing command that, on the owner's explicit decision, switches a delegated-child plan with no recorded delegation, no execution other than a closed child attempt that never launched, and task content diverged from the pre-snapshot to a supervisor-retained plan with policy owner-approved. The command SHALL require a non-empty owner approval statement and reason and SHALL record them with the approval time and the diverged paths in the plan. It SHALL NOT record a delegation, launch claim or escalation and SHALL leave the routed profile unchanged. It SHALL be refused, leaving the routing record unchanged, when the plan is already supervisor-retained, a real delegation was recorded, an execution other than a closed never-launched child attempt exists, task content is unchanged, or the approval or reason is empty. A never-launched attempt SHALL be kept as prior execution of the retained outcome. A retained execution recorded under this policy SHALL carry the approval, the early and archive routing gates SHALL accept it, and routing reports SHALL mark the record owner-approved. A plan claiming the owner-approved policy without a complete recorded approval SHALL be invalid.

#### Scenario: Owner approves a supervisor-written diff

- **GIVEN** a delegated-child plan with no delegation and diverged task content
- **WHEN** the owner-approved retention is recorded with the owner's statement and a reason
- **THEN** the plan becomes supervisor-retained with policy owner-approved and the recorded approval
- **AND** the early gate passes, the retained execution records the approval and the archive gate passes

#### Scenario: Approval refused

- **WHEN** the approval or reason is empty, the plan is already retained, a real delegation or an execution other than a never-launched attempt exists, or task content is unchanged
- **THEN** the command fails naming the reason and the routing record is unchanged

#### Scenario: Approval after a never-launched child attempt

- **GIVEN** a delegated-child plan whose only recorded execution is a closed child attempt that never launched, and diverged task content
- **WHEN** the owner-approved retention is recorded and finalized
- **THEN** the plan becomes supervisor-retained with policy owner-approved and the retained execution keeps the attempt as prior execution

#### Scenario: Forged policy

- **WHEN** a routing record claims the owner-approved policy without a complete recorded approval
- **THEN** reading the record fails plan validation

## MODIFIED Requirements

### Requirement: Retained execution is declared up front and recovery never fabricates evidence

Recording a retained outcome SHALL require a supervisor-retained plan declared at route time, or recorded through an explicit owner-approved retention, and SHALL only finalize it with the containment postcheck. Apart from that explicit owner-approved retention, the platform SHALL NOT convert a delegated-child plan into retained execution after task content changed, SHALL NOT accept a Claude execution without an open delegation, and SHALL NOT permit an escalation to a supervisor-retained plan without a real recorded delegation or unchanged task content. No recovery path SHALL write a launch claim, retrospective delegation or escalation trigger that did not occur.

#### Scenario: Retained outcome after up-front plan

- **GIVEN** a supervisor-retained plan
- **WHEN** implementation completes and the retained outcome is recorded
- **THEN** the record is a real retained execution with a clean postcheck and the terminal gate passes

#### Scenario: Late switch to retention

- **GIVEN** a delegated-child plan with diverged task content and no delegation
- **WHEN** a retained outcome or escalation to retention is attempted
- **THEN** the operation is refused and names the explicit owner-approved retention as the only way to record the owner's decision

#### Scenario: Escalation after a real delegation

- **GIVEN** a recorded real delegation whose result was reviewed
- **WHEN** a recorded escalation with a concrete reason switches the plan to retention
- **THEN** the escalation is accepted and provenance keeps the delegation and the escalation distinct

#### Scenario: Unlaunched Codex attempt

- **WHEN** Codex is refused or fails before its child process starts
- **THEN** the attempt is closed with outcome not-launched and no open delegation remains
- **AND** subsequent supervisor writes fail the early gate and cannot authorize retention or escalation without an explicit owner-approved retention

#### Scenario: Lifecycle rename hides a source deletion

- **WHEN** a tracked implementation path is moved into an excluded lifecycle directory
- **THEN** divergence includes the source path for both staged and committed changes
- **AND** routing, late delegation and escalation cannot bypass the unchanged-content requirement

#### Scenario: Recovery preserves child safety and outcome

- **GIVEN** a failed child execution
- **WHEN** re-routing, escalation or retained finalization is requested
- **THEN** unresolved containment violations and unreleased or ambiguous Codex writers block the request
- **AND** retained finalization after an accepted escalation preserves the prior child execution, delegation and escalation as distinct provenance

#### Scenario: Fresh source checkout runs checks

- **GIVEN** committed managed package metadata without local managed task state
- **WHEN** the check/test entrypoint runs in a fresh source checkout
- **THEN** checks remain available without resolving private executor lineage

#### Scenario: Recovery without a saved execution receipt

- **GIVEN** an existing route whose child escaped its containment boundary before an execution receipt was saved
- **WHEN** re-routing is requested
- **THEN** the original containment boundary is checked and the violation blocks recovery

#### Scenario: Failed child retry retains provenance

- **WHEN** an attributable failed Codex child is re-routed
- **THEN** the complete prior route including executor identity, execution and escalation history remains in retry provenance and subsequent durable records
