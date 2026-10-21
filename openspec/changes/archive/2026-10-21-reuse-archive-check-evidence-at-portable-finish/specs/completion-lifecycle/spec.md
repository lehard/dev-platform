## ADDED Requirements

### Requirement: Portable finish reuses archive check evidence for the exact validated tree

In the `portable` lifecycle, `finish` for a managed delivery SHALL NOT execute the selected local checks again when the selected-check evidence produced by archive proves that the tree being published passed the checks finish requires. Reuse SHALL require evidence bound to the current managed checkout and task content, a recorded validated base equal to the current merge base with the remote main that `HEAD` contains, a current required selection that is ready, and a successful executed command for every command of that selection. Finish SHALL print whether the evidence was reused or why it was not. When reuse is not proven, finish SHALL run the required validation as before. Unreadable, failed or mismatched evidence SHALL continue to stop publication. The coordinator lifecycle, non-managed delivery, OpenSpec hygiene and the final pull request CI SHALL be unchanged.

#### Scenario: Unchanged archived content

- **GIVEN** a managed task in a `portable` project whose archive executed the selected checks successfully and wrote version-2 evidence
- **AND** only the archive materialization and lifecycle evidence changed afterwards and main did not advance
- **WHEN** finish runs
- **THEN** finish prints that the archive evidence was reused
- **AND** the selected checks are executed once over archive and finish

#### Scenario: Task content changed after archive

- **WHEN** a source or test path of the task changes after the archive validation
- **THEN** the existing evidence gate stops publication, naming the stale evidence

#### Scenario: Base changed after archive

- **GIVEN** main advanced after archive and the task branch was reconciled with it
- **WHEN** finish runs
- **THEN** finish prints that the evidence is not reusable because the validated base differs
- **AND** finish executes the required checks

#### Scenario: Required selection not covered

- **WHEN** the selection finish requires now contains a command that the evidence does not show as executed successfully
- **THEN** finish prints the uncovered command as the reason and executes the required checks

#### Scenario: Coordinator lifecycle unchanged

- **WHEN** finish runs in the coordinator lifecycle
- **THEN** no reuse decision is made and validation behaves as before
