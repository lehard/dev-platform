## ADDED Requirements

### Requirement: A quick task re-admits a descendant head through finish

When an admitted quick task waits in a re-admission state with no live claim on its offered job, `finish` on the same PR SHALL supersede the admitted head with a descendant head and record that supersession. The candidate SHALL return to `ready` without a review job and SHALL pass integration and exact-head required CI. Anything else SHALL be refused naming the cause, and the PR SHALL NOT need closing or republishing.

#### Scenario: Fix of a red required check reaches the queue

- **GIVEN** a quick task whose required check failed and left it `integration-repair-pending` on its proven head
- **WHEN** the developer commits a fix on top of the proven head and runs `finish`
- **THEN** the admission records `supersedes` with the proven head, its state and the reason
- **AND** the new head is `ready` on the same PR with no review job

#### Scenario: Head already pushed

- **GIVEN** a descendant head already on the PR of a quick task in a re-admission state
- **WHEN** the developer runs `finish`
- **THEN** the supersession is recorded for that head

#### Scenario: Refused supersession

- **WHEN** the offered job holds a live claim, the new head does not descend from the proven head, or the identity is not a quick task on the same branch
- **THEN** `finish` fails naming the cause and writes no admission

#### Scenario: Managed candidates keep their path

- **WHEN** a managed candidate is re-admitted
- **THEN** it still needs its developer handoff and returns to `review-pending`

### Requirement: Status names the developer exit of a quick task with a red CI

For a quick task with a failed required check, `status` and `next_action` SHALL name the developer path for the current step and SHALL NOT name a coordinator decision.

#### Scenario: Red check not yet recorded

- **GIVEN** a quick task whose required check failed before the queue recorded it
- **WHEN** status is read
- **THEN** it says to wait for the queue record, then fix on top of the proven head and run `finish`

#### Scenario: Red check recorded

- **GIVEN** a quick task waiting in `integration-repair-pending` at its PR head
- **WHEN** status is read
- **THEN** `next_action` names the proven head and says to commit a fix on top of it and run `finish`

#### Scenario: Head already pushed

- **GIVEN** a descendant head pushed over the proven head
- **WHEN** status is read
- **THEN** the owner is developer re-admission and `next_action` says to run `finish`

#### Scenario: Local head off the proven head

- **GIVEN** a local head that does not descend from the proven head
- **WHEN** `finish` or status observes it
- **THEN** the message names the proven head and how to bring the worktree to it

### Requirement: An admitted quick head moves only with a recorded transition

Among platform commands only `finish` SHALL move the head of an admitted quick task, recording the transition in the same run. A head without a recorded transition SHALL NOT integrate or merge.

#### Scenario: Reconcile of an admitted quick task

- **GIVEN** an admitted quick task behind main
- **WHEN** the developer runs reconcile
- **THEN** main is merged locally, nothing is pushed and the output names `finish`

#### Scenario: Reconcile outside the queue

- **WHEN** reconcile runs for a task with no queue admission, or in a portable project
- **THEN** it behaves as before and does not load the coordinator stack

#### Scenario: Raw push over an admitted quick head

- **GIVEN** a head pushed outside the platform over an admitted quick head
- **WHEN** the queue runs
- **THEN** it does not integrate or merge that head

#### Scenario: Interrupted finish

- **GIVEN** a `finish` that pushed the head and stopped before recording the transition
- **WHEN** `finish` runs again
- **THEN** the transition is recorded for the same head
