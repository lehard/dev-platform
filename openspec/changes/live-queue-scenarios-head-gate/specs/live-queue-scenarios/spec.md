## ADDED Requirements

### Requirement: Queue path scenarios run on real GitHub

The scenarios SHALL include a managed task through review, finalize and queue to MERGED, a red required CI with its exit, and a conflict with main through integration repair. Review SHALL run through the real worker with a scripted reviewer behind the documented reviewer binary override, and repair SHALL run through the worker `--llm-command` path with a scripted writer. GitHub, queue, claims, labels and CI SHALL be real.

#### Scenario: Red CI recovers

- **GIVEN** a candidate whose required CI fails on its head
- **WHEN** the scenario follows the path the queue offers
- **THEN** the candidate reaches MERGED with no step outside documented entrypoints

#### Scenario: Conflict with main

- **GIVEN** main moved with a conflicting change after admission
- **WHEN** the queue offers integration repair and the scripted executor resolves it
- **THEN** the candidate reaches MERGED on its repaired head

### Requirement: Queue and lifecycle changes carry a scenario receipt

A run on a candidate head SHALL write a receipt bound to task content with a result per scenario. Handoff of a change touching declared queue or lifecycle paths SHALL be refused when the receipt is missing, bound to other content, or holds a red scenario outside the known failure list. An unavailable sandbox SHALL fail explicitly.

#### Scenario: Receipt is missing

- **GIVEN** a change touches a declared queue path and has no receipt for its content
- **WHEN** handoff runs
- **THEN** it refuses naming the missing receipt

#### Scenario: Known failure

- **GIVEN** the receipt holds a red scenario listed as a known failure with its defect
- **WHEN** handoff runs
- **THEN** the known failure is reported and does not block
