## ADDED Requirements

### Requirement: A developer fix re-admits a candidate waiting for integration repair

The coordinator SHALL accept a fresh developer handoff for a candidate whose latest record is `integration-repair-pending` when the record is bound to the proven integrated head, the handoff names the same task, the offered integration-repair job holds no live claim, and the new head descends from the proven head. The accepted handoff SHALL supersede the published integration-repair job. An archived managed task whose admitted PR waits in `integration-repair-pending` SHALL be re-opened for that handoff when the local head strictly descends from the proven head. A live claim, a different task or a head that does not descend from the proven head SHALL be refused with a message naming the reason.

#### Scenario: Developer fix of a red integrated check is re-admitted
- **GIVEN** a candidate in `integration-repair-pending` after a required check failed on its integrated head, with no live claim on its integration-repair job
- **WHEN** the developer hands off a fix commit on top of the integrated head
- **THEN** the handoff is admitted for review and the integration-repair job is no longer offered

#### Scenario: Claimed integration repair refuses the developer fix
- **GIVEN** a candidate in `integration-repair-pending` whose integration-repair job is claimed by a live writer
- **WHEN** the developer hands off a fix
- **THEN** the handoff is refused naming the claim

#### Scenario: Unrelated head refuses the developer fix
- **GIVEN** a candidate in `integration-repair-pending`
- **WHEN** the developer hands off a head that does not descend from the integrated head
- **THEN** the handoff is refused naming the missing ancestry

### Requirement: An integration-repair writer receives the failed check's evidence

When integration repair is needed because a required check failed on the integrated candidate, the red gate SHALL record the identity of each failed required check, including its name and log link. The integration-repair writer brief SHALL carry, for each failed check, its identity and a bounded excerpt of its failed log. A writer brief for a failed required check without that identity or with an unreadable log SHALL be refused before any writer starts, naming the cause, and SHALL NOT spend an integration-repair attempt.

#### Scenario: Writer brief carries the failed log
- **GIVEN** an integration-repair job for a failed required check whose log is readable
- **WHEN** the operator runs the job
- **THEN** the writer brief names the failed check and includes the excerpt of its failed log

#### Scenario: Brief without evidence is refused
- **GIVEN** an integration-repair job for a failed required check whose red gate has no failed-check identity
- **WHEN** the operator runs the job
- **THEN** no writer starts and the run fails naming the missing evidence
