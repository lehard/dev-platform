# platform-lifecycle Specification Delta

## ADDED Requirements

### Requirement: Shared candidates grow append-only and are draft until complete

A shared Requirement candidate manifest SHALL list the expected mandatory changes and the verified children present so far. An incomplete candidate SHALL be published only as a draft PR on its stable branch and manifest path. A new manifest revision SHALL keep earlier children as an exact prefix with identical heads and SHALL be pushed only as a fast-forward. Marking the PR ready, arming merge, publication-queue admission and terminal reconciliation SHALL require a complete manifest, the Requirement retrospective checkpoint and full checks on the exact final head.

#### Scenario: Later child is appended

- **GIVEN** a draft candidate PR exists for the first verified child
- **WHEN** the next child is ready
- **THEN** its exact delta is added as new commits on the same branch and the manifest is extended
- **AND** the same PR is updated by fast-forward push without a force push or duplicate

#### Scenario: Divergent or reordered growth is refused

- **GIVEN** an existing candidate branch
- **WHEN** a revision changes, removes or reorders an earlier child, a child head changed, or the branch is not a fast-forward
- **THEN** publication stops before any push or PR mutation naming the exact boundary

#### Scenario: Interrupted run resumes

- **GIVEN** a draft or ready candidate PR already exists for the exact branch
- **WHEN** the supervisor is rerun
- **THEN** it resumes that branch and PR without creating another PR or candidate

#### Scenario: Completion applies the final gates

- **GIVEN** every mandatory child is present
- **WHEN** the candidate is made ready
- **THEN** the retrospective checkpoint exists and full checks pass on the exact final head before the existing protected merge path runs
