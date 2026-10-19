## ADDED Requirements

### Requirement: Archive rejects a new capability without an authored Purpose before mutation

Before review, selected checks, evidence writes or any OpenSpec mutation, the archive lifecycle SHALL reject a change whose delta creates a capability absent from the main specs unless that delta carries a non-empty, non-placeholder `## Purpose`. A placeholder SHALL include `TBD`, `TODO` or `FIXME` text and the sentence OpenSpec archive writes for a missing Purpose. The diagnostic SHALL name the delta file and the missing section. When the delta carries an authored Purpose, archive SHALL write it to the new main spec and the archived tree SHALL pass `openspec validate --all --strict` without manual edits.

#### Scenario: New capability delta without Purpose
- **GIVEN** an active change whose delta creates capability `foo` with no `## Purpose`
- **WHEN** archive is requested
- **THEN** archive fails naming `specs/foo/spec.md` and the missing Purpose
- **AND** the change remains active, no main spec is written and no evidence is written

#### Scenario: Placeholder Purpose
- **WHEN** the new-capability delta Purpose is `TBD` or the archive placeholder sentence
- **THEN** archive fails before mutation with the same diagnostic

#### Scenario: Authored Purpose
- **GIVEN** the new-capability delta carries an authored `## Purpose`
- **WHEN** archive completes
- **THEN** the main spec Purpose is the authored text
- **AND** `openspec validate --all --strict` passes with no `TBD` in `openspec/specs`

### Requirement: Archive requires a committed package before expensive work

For a non-finalization archive, the lifecycle SHALL reject uncommitted or untracked authored files of the change (proposal, design, tasks, delta specs, verification receipt) and of the main specs before review, selected checks or evidence writes. Evidence files that the lifecycle helpers themselves generate SHALL NOT block. The diagnostic SHALL list the paths and the commit command.

#### Scenario: Uncommitted tasks or receipt
- **GIVEN** `tasks.md` or `verification.md` of the change has uncommitted edits
- **WHEN** archive is requested
- **THEN** archive fails naming those paths and the commit command
- **AND** no review, selected check or evidence write runs

### Requirement: Archive is rehearsed and recoverable

Before mutating the checkout, archive SHALL run `openspec archive` and `openspec validate --all --strict` on a disposable copy of the OpenSpec tree and SHALL stop with the failing items if either fails, leaving the checkout unchanged. If the real post-archive strict validation still fails, the lifecycle SHALL restore the exact OpenSpec tree captured immediately before the real archive, SHALL exit non-zero with the failing items, and SHALL allow the same archive command to be rerun after the fix without manual spec edits.

#### Scenario: Rehearsal fails
- **WHEN** rehearsal strict validation fails
- **THEN** archive exits non-zero with the failing items
- **AND** the change is still active and `openspec/specs` is unchanged

#### Scenario: Real post-validation fails
- **GIVEN** rehearsal passed but the real `validate --all --strict` fails
- **WHEN** archive handles the failure
- **THEN** the pre-archive OpenSpec tree is restored exactly
- **AND** the error names the failing items and states that the same command can be rerun

### Requirement: Archive failures report failing items

Archive, rehearsal, recovery and post-review finalization SHALL report OpenSpec failures by their failing items and diagnostics, not by a fixed-length tail of combined output. When no failing item line is recognisable, the whole output SHALL be reported.

#### Scenario: Finalization archive fails on validation
- **WHEN** finalization archive fails because strict validation rejects an item
- **THEN** the error contains that item and its reason
- **AND** progress or INFO lines alone are never the reported cause

### Requirement: Archive readiness is checked before review spend

Developer handoff, offering or launching a composition review, and composition finalization SHALL evaluate the same archive-content readiness predicate (all tasks complete; meaningful Purpose for each capability first created in contribution order) and SHALL stop with the named children and problems before spending a review round or archiving any child.

#### Scenario: Composition child has unticked tasks
- **GIVEN** a complete Requirement composition whose child has an unticked task
- **WHEN** the composition draft is published or a composition review job starts
- **THEN** no review is offered or launched
- **AND** the error names the child and its incomplete tasks

#### Scenario: Finalization meets a child without Purpose
- **WHEN** composition finalization starts and a child creates a capability without an authored Purpose
- **THEN** finalization fails before archiving any child, naming the child and delta

#### Scenario: Archive and hygiene stay compatible
- **WHEN** archive runs its validation subprocess for its exact completed target
- **THEN** lifecycle hygiene still exempts only that target
