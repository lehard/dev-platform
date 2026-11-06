## MODIFIED Requirements

### Requirement: Required independent review is an automatic, resumable lifecycle gate

When independent review is required, a missing or stale review of a managed change SHALL be run outside archive before finalize; finalize SHALL only require current review evidence and never launch a review. The lifecycle SHALL re-validate current review evidence before publication and SHALL expose the derived review state and next command through task status and Requirement advance from file-backed evidence without a separate state store.

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
- **GIVEN** a quick task whose diff touches no protected path
- **WHEN** it completes
- **THEN** no independent review is required

### Requirement: Finish finalizes the change

Finish SHALL run the independent review when `[independent_review] enabled = true` and the change is risky, and then the shared finalize function on the verified active change before publication, and Requirement advance SHALL finalize a ready multi-child child the same way. Without that setting the review stays optional and can be run by hand with `scripts/independent_review.py`.

#### Scenario: Project finishes
- **WHEN** finish runs on a verified active change
- **THEN** the change is archived through finalize and committed before publication

## REMOVED Requirements

### Requirement: Independent review applies only to managed changes in enabling repositories

**Reason**: Review now follows the risk of the change, not its provenance.
**Migration**: See "Independent review applies to risky changes in enabling repositories".

## ADDED Requirements

### Requirement: Independent review applies to risky changes in enabling repositories

Independent review SHALL be required exactly when the repository enables it and the change is risky, for quick and managed tasks alike. `finish` SHALL launch no reviewer for any other change.

#### Scenario: Risky change in an enabling repository

- **GIVEN** a repository with `[independent_review] enabled = true`
- **WHEN** a quick or managed task whose diff touches a protected path reaches `finish`
- **THEN** independent review is required

#### Scenario: Other change in an enabling repository

- **GIVEN** a repository with `[independent_review] enabled = true`
- **WHEN** a quick or managed task whose diff touches no protected path reaches `finish`
- **THEN** no reviewer is launched and `finish` says so

#### Scenario: Repository that does not enable review

- **WHEN** a task reaches `finish` in a repository without `[independent_review] enabled = true`
- **THEN** no reviewer is launched

### Requirement: A risky change is decided from the task diff and the protected surface

A change SHALL be risky exactly when the task's own diff against its merge base with authoritative main, without declared generated files, touches a path matching a `[[protected]]` entry of the protected surface. The decision SHALL read nothing else. In the platform source layout a path SHALL be compared in its rendered form.

#### Scenario: Only a generated file changed

- **WHEN** the only protected path in the diff is a declared generated file
- **THEN** the change is not risky

#### Scenario: Template source of a protected file changed

- **GIVEN** the platform source layout
- **WHEN** the diff touches `template/scripts/finish_task.py`
- **THEN** the change is risky

#### Scenario: Protected surface cannot be read

- **GIVEN** review is enabled
- **WHEN** no protected surface or more than one is found, or its list is unreadable or empty
- **THEN** the task stops with an error naming the problem
- **AND** the change is not treated as non-risky

### Requirement: Quick task review evidence is local and bound to content

The review request, reports and dispositions of a quick task SHALL live in its own git directory and SHALL NOT enter the task's history. They SHALL be bound to the quick task content identity.

#### Scenario: Rerun with unchanged content

- **GIVEN** a quick task with a passed review
- **WHEN** `finish` runs again and the task content did not change
- **THEN** no reviewer is launched

#### Scenario: Content changes after review

- **WHEN** the task content changes after a passed review
- **THEN** the evidence is stale and `finish` launches a new review

### Requirement: Finish stops a risky quick task that the reviewer did not pass

For a risky quick task `finish` SHALL run the review after validation and before any publication, and `--no-checks` SHALL NOT skip it. It SHALL NOT repair a finding or retry with another provider.

#### Scenario: Material finding

- **WHEN** a reviewer reports a material finding
- **THEN** `finish` stops before any PR is opened or updated
- **AND** the message names the finding and the next commands: fix, commit and rerun `finish`, or reject it with a rationale

#### Scenario: Reviewer could not run

- **WHEN** the reviewer cannot start, fails, times out or returns malformed output
- **THEN** `finish` stops before any PR is opened or updated with an error naming the cause
