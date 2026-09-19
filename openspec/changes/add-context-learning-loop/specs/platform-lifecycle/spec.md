## ADDED Requirements

### Requirement: Friction learning can represent project-context gaps without self-modifying context

Platform friction SHALL support a bounded `context-gap` classification for high-signal evidence that an agent lacked, misread, or repeatedly guessed stable project/domain context. Context-gap evidence SHALL reuse the existing sanitized friction/process-learning pipeline and SHALL NOT automatically rewrite canonical project context or create managed work.

#### Scenario: User correction reveals missing project context
- **WHEN** a user correction or substantive task failure shows that the agent lacked or misinterpreted stable project/domain context
- **THEN** the existing friction path can record the event as a `context-gap`
- **AND** the event identifies a bounded concern such as product, domain, architecture, anti-pattern, example, or other project-context destination
- **AND** stored/routed evidence remains sanitized and excludes raw sensitive transcripts.

#### Scenario: Same context gap recurs across executions
- **WHEN** materially equivalent context-gap evidence recurs, including across different model or provider identities
- **THEN** the existing deduplication/root-cause path strengthens or updates one bounded evidence identity instead of creating a second failure-log system
- **AND** model/provider identity is not part of the root-cause fingerprint merely because the executor changed.

#### Scenario: Repetition reaches an arbitrary count
- **WHEN** the same context gap has been observed three or more times
- **THEN** repetition is available as evidence strength
- **BUT** the platform does not automatically modify canonical context
- **AND** does not automatically create or start a managed task solely because that count was reached.

### Requirement: Process review distinguishes context improvements from process/tooling fixes

Process Health Review SHALL be able to distinguish context-gap evidence from ordinary tooling/process friction and surface a bounded proposed context destination/improvement when current evidence supports that classification. The review remains advisory and read-only until a human explicitly accepts work.

#### Scenario: Review finds a recurring context root cause
- **WHEN** a review clusters multiple context-gap observations around the same likely root cause
- **THEN** the report identifies the contributing evidence and the likely context concern/destination to improve
- **AND** keeps observation, evidence, hypothesis, and proposal distinct
- **AND** does not create a managed task or edit canonical context.

#### Scenario: Evidence is actually a tooling/process defect
- **WHEN** the observed failure is better explained by lifecycle, tooling, CI, worktree, authentication, or process behavior
- **THEN** the review keeps it in the ordinary process-friction path
- **AND** does not misclassify it as a project-context defect merely because an agent made an error.

### Requirement: Accepted context improvements use the ordinary managed lifecycle

A proposed context improvement SHALL become repository work only after explicit human acceptance and SHALL then use the ordinary managed-task/OpenSpec lifecycle appropriate to the target repository.

#### Scenario: Human accepts a context improvement candidate
- **WHEN** a human explicitly accepts a reviewed context-gap proposal as work
- **THEN** the platform creates or reuses the normal managed task through the existing intake contract
- **AND** context evidence is linked as provenance where supported
- **AND** no parallel context-specific task state machine is introduced.
