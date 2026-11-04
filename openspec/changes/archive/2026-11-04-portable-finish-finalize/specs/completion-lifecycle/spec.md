## MODIFIED Requirements

### Requirement: Portable archive reuses selected-check evidence by the finish rule

Portable finalize, run by finish, SHALL decide by the rule finish uses (`check_evidence_reuse`) before running the selected checks: reusable evidence SHALL be reused and the decision printed, and otherwise the selected checks SHALL run as before.

#### Scenario: Portable archive with reusable evidence

- **WHEN** portable finalize finds reusable evidence
- **THEN** it reuses the evidence and prints the decision

#### Scenario: Portable archive without reusable evidence

- **WHEN** portable finalize finds no reusable evidence
- **THEN** the selected checks run as before

## ADDED Requirements

### Requirement: Without a queue finish finalizes the change

Without the publication queue, finish SHALL run a required independent review and then the shared finalize function on the verified active change before publication, and Requirement advance SHALL finalize a ready portable multi-child child the same way.

#### Scenario: Light project finishes
- **WHEN** finish runs in a light project on a verified active change
- **THEN** the change is archived through finalize and committed before publication

### Requirement: The developer archive command refuses

`openspec_lifecycle.py archive` without `--finalize` SHALL refuse before any work, naming finish or the queue finalize job as the archive executor.

#### Scenario: Developer runs archive
- **WHEN** a developer runs archive for an active change
- **THEN** it fails naming the executor and the change stays active
