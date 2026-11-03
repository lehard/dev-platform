## MODIFIED Requirements

### Requirement: Required independent review is an automatic, resumable lifecycle gate

When independent review is required, a missing or stale review SHALL be run outside archive before finalize; finalize SHALL only require current review evidence and never launch a review. The lifecycle SHALL re-validate current review evidence before publication and SHALL expose the derived review state and next command through task status and Requirement advance from file-backed evidence without a separate state store.

#### Scenario: Archive runs without prior review
- **GIVEN** a required managed change with no current review evidence
- **WHEN** the archive helper runs
- **THEN** it launches no review
- **AND** it fails listing the missing review evidence among the unmet preconditions

#### Scenario: Finish with stale review
- **GIVEN** the candidate changed after review
- **WHEN** finish is invoked
- **THEN** publication is refused before any remote mutation with an instruction to rerun review

#### Scenario: New session resumes
- **WHEN** a new Codex or Claude Code session reads task status or Requirement advance
- **THEN** it sees the review state and the exact next command

#### Scenario: Quick task
- **GIVEN** work without managed provenance
- **WHEN** it completes
- **THEN** no independent review is required

## ADDED Requirements

### Requirement: One finalize function archives a change

An OpenSpec change SHALL be archived only through one finalize function that checks its preconditions, validates, rehearses and archives with recovery. The queue finalize job SHALL archive through it.

#### Scenario: Finalize job archives
- **WHEN** the queue finalize job archives a reviewed candidate
- **THEN** it calls the finalize function and the archive, commit and path checks are as before

### Requirement: Finalize reports every unmet archive precondition at once

Before any archive work, finalize SHALL evaluate every archive precondition (tasks, verification receipt, review evidence, routing, automated-check evidence, committed package, private lineage, checkout identity) and SHALL fail once, listing each unmet precondition with its fix.

#### Scenario: Several preconditions are missing
- **WHEN** a change lacks review evidence and has an unticked task
- **THEN** finalize fails once naming both with their fixes and archives nothing
