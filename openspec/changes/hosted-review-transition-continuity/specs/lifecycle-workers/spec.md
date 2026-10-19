## ADDED Requirements

### Requirement: Coordinator friction is attributed by public work identity

The coordinator friction sink SHALL attribute an event to the Requirement through the public work identity encoded in the managed candidate branch (`BR-N` for the Requirement, `BR-N/TM` for a child), derived without reading runner configuration, the Development Backlog or any other source. An unmanaged branch SHALL be recorded as having no Requirement; a branch that looks managed but whose identity is malformed SHALL fail friction recording explicitly, naming the branch. The same attribution SHALL be produced by hosted and local coordinators.

#### Scenario: Hosted review with material findings records friction
- **GIVEN** a managed candidate and a hosted contract without Development Backlog configuration
- **WHEN** a hosted review finds material findings
- **THEN** one run records `repair-pending` and a trusted coordinator evidence record bound to the Requirement's work identity
- **AND** no further review round or evidence commit is created

#### Scenario: Malformed managed branch
- **WHEN** friction must be recorded for a candidate whose branch looks managed but carries a malformed identity
- **THEN** recording fails with an error naming the branch
- **AND** no transition is published without durable friction

### Requirement: A review job proves friction can be attributed before it reviews

A review or repair job SHALL derive the friction attribution of its candidate after its claim is validated and before the reviewer or writer starts and before any evidence push. When it cannot, the job SHALL fail explicitly with the named cause and SHALL NOT move the candidate head.

#### Scenario: Attribution unavailable
- **WHEN** a hosted review job claims a candidate whose friction attribution cannot be derived
- **THEN** the run fails before the reviewer starts, naming the cause
- **AND** the candidate head and records are unchanged

### Requirement: A worker's own push is not mistaken for a foreign head change

After a successful lease-protected push of its validated result, a worker SHALL wait a bounded time for the pull request head to report the pushed head before deciding the job's outcome. A head that becomes any other commit, or a claim that changes, SHALL still discard the job. A head that does not converge within the bound SHALL fail the job explicitly with the cause instead of discarding it silently.

#### Scenario: Pull request head lags behind the push
- **WHEN** the pull request API still reports the job head immediately after the worker's own successful push and then reports the pushed head
- **THEN** the job publishes its transition for the pushed head and is not discarded

#### Scenario: Someone else moves the head
- **WHEN** the pull request head becomes a commit other than the job head or the pushed head, or the claim changes
- **THEN** the job is discarded and nothing is published for it

### Requirement: Content-bound gates survive trusted harness pushes

Gates bound to task-content identity SHALL remain valid on a head reached through a trusted harness push of the same candidate when the task-content digest is unchanged, including when an interrupted job is recovered from its validated-push receipt and when the next job claims that head. Gates bound only to an older head SHALL NOT survive a head move. A coordinator command SHALL restore content-bound gates already lost on a candidate in `finalize-pending`, `review-pending` or `blocked-retryable` only after proving every head move from a record holding those gates to the current head was a trusted harness push with the same task-content digest; any other history SHALL be refused, naming the failing step. Restoration SHALL NOT run a review, register a claim, rewrite branch history or bypass a gate.

#### Scenario: Review without material findings keeps admission gates
- **WHEN** a hosted review without material findings pushes its evidence and records `finalize-pending`
- **THEN** the record carries the admission gates `semantic-verification`, `selected-checks` and `developer-friction` with the review gate
- **AND** a later finalize job with an unchanged content digest does not require fresh semantic verification

#### Scenario: Restoring gates lost before the fix
- **GIVEN** a `finalize-pending` candidate whose admission gates were lost across trusted review-evidence pushes with an unchanged content digest
- **WHEN** the operator runs the restore command
- **THEN** one record on the current head carries the restored gates and the state is unchanged

#### Scenario: Restoration across a foreign push
- **WHEN** any head move between the gated record and the current head lacks a trusted harness push receipt or changed the content digest
- **THEN** the restore command refuses, naming that head move, and publishes nothing
