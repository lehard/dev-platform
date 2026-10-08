## ADDED Requirements

### Requirement: Complete validated lifecycle comment history

The platform SHALL read the complete ordered PR comment history needed for lifecycle marker replay, including histories exceeding one GitHub API page. It SHALL validate the complete observation before returning comments to lifecycle consumers. A transport error or malformed page, comment record or ordering SHALL fail explicitly with an error naming comment-history acquisition and SHALL NOT yield a truncated or filtered history.

#### Scenario: History spans multiple pages

- **WHEN** a PR has 101 or more comments and a lifecycle marker occurs after the first 100 comments
- **THEN** the history reader returns every comment in API order and the marker is available to the existing authenticated replay rules

#### Scenario: History ends at an exact page boundary

- **WHEN** the complete history contains exactly 100 or 200 comments
- **THEN** the reader returns the complete history without treating a full page as an error

#### Scenario: Empty history

- **WHEN** GitHub returns a valid empty comment page
- **THEN** the reader returns an empty history

#### Scenario: Missing response is not an empty history

- **WHEN** the response body is empty or contains no pages
- **THEN** the operation fails explicitly instead of returning an empty history

#### Scenario: Later page is unavailable

- **WHEN** pagination fails after an earlier page was received
- **THEN** the operation fails with an error naming comment-history acquisition and no earlier-page prefix is consumed

#### Scenario: Malformed observation

- **WHEN** the response contains invalid JSON, a non-array page, a non-object comment record, a record without an integer id, or ids that are not strictly increasing in API order
- **THEN** the operation fails explicitly without dropping records or returning a partial history

### Requirement: Exact-head required-check observation

The platform SHALL derive the required-check state of a pull request from valid structured GitHub check output, SHALL resolve the required set from the pull request's final protected target (the main branch for main-targeted pull requests and for Requirement contribution pull requests targeting a `requirement/BR-<n>` integration branch), and SHALL bind the snapshot to the expected PR head both before and after reading the checks. Passed, pending, failed and not-registered observations SHALL remain distinct from unusable observations, which SHALL carry an explicit cause (transport failure, malformed output, head mismatch or unsupported state) and SHALL NOT authorize publication. The no-required-checks condition SHALL be resolved from the base branch's protection, not from CLI wording. A pending check or a repairable failed check SHALL NOT terminally block a candidate; an unusable observation SHALL be reported with its cause and SHALL NOT be substituted by an assumed state.

#### Scenario: Successful check snapshot

- **WHEN** gh returns a valid JSON list whose required checks all passed on the expected head
- **THEN** the observation is passed

#### Scenario: Pending check snapshot

- **WHEN** gh returns a valid JSON list containing an in-progress required check on the expected head
- **THEN** the observation is pending and the coordinator waits without blocking the candidate

#### Scenario: Failed check snapshot

- **WHEN** gh returns a valid JSON list containing a failed required check on the expected head
- **THEN** the observation is failed and the candidate enters the bounded repair path instead of a terminal block

#### Scenario: Contribution uses the main branch's required checks

- **WHEN** a contribution pull request targets an unprotected `requirement/BR-<n>` integration branch and main requires the `validate` check
- **THEN** the observation is derived from the contribution's `validate` check, a missing `validate` row is pending, and the contribution can record a passed required-checks gate once `validate` succeeds

#### Scenario: Contribution preserves required App binding

- **WHEN** main requires a check from a specific App and a contribution has a successful check of the same name from another App
- **THEN** that success does not satisfy the requirement; the required App's missing run remains pending, and only its exact-head run determines the bound check state

#### Scenario: Base branch requires no checks

- **WHEN** gh reports no required checks for a main-targeted pull request and the base branch protection requires no status checks
- **THEN** the observation is not-registered with a detail naming the base branch, decided from branch protection rather than CLI text

#### Scenario: Unusable observation

- **WHEN** gh exits with an unexpected status, its output is not valid JSON, gh reports no required checks while the base requires some, or the PR head differs from the expected head before or after the checks are read
- **THEN** the observation is unusable with a cause of transport, malformed or head-mismatch and cannot authorize publication

#### Scenario: Transport or head fault does not terminally block

- **WHEN** the coordinator receives an unusable observation caused by transport failure or head mismatch while integrating a candidate
- **THEN** it reports a non-terminal waiting result naming the cause and does not mark the candidate blocked

### Requirement: Trust configuration fails closed

The platform SHALL read every configured coordinator trust source under its explicit configuration contract and SHALL raise an error naming the source when a configured source is unreadable or invalid. It SHALL NOT silently narrow the trusted set. Only the documented absence of an optional source (unset environment variable, no project config, disabled operator config, no publication table or key) SHALL be treated as no contribution from that source.

#### Scenario: Invalid trust source

- **WHEN** the platform config cannot be parsed, an enabled operator config is missing or invalid, the publication table is not a table, or the configured coordinator App is not a string
- **THEN** the operation fails explicitly naming the source and no trusted set is derived

#### Scenario: Absent optional source

- **WHEN** the operator config is disabled or no publication table is configured
- **THEN** the remaining valid sources define the trusted set without error

#### Scenario: Consumers do not continue with narrowed trust

- **WHEN** a lifecycle consumer (admission or a lifecycle worker) needs the trusted set and a configured source is invalid
- **THEN** the consumer stops with the named error instead of continuing

### Requirement: Managed admission requires exact task-content provenance

The platform SHALL require valid exact task-content provenance, bound to the admitted head, before admitting a managed candidate, and SHALL fail explicitly when that provenance is missing, unreadable, invalid or cannot be bound to the admitted head. A failure to obtain managed provenance SHALL NOT produce a quick-task branch/head identity. Only a candidate that the validated lifecycle identifies as a genuine quick task without a managed package SHALL receive the quick-task identity.

#### Scenario: Managed proof unavailable

- **WHEN** a managed candidate's task state is unreadable, its checkout is not at the admitted head, or its task-content proof is missing or has no digest
- **THEN** admission fails with an error naming the missing provenance and writes no admission record or branch/head identity

#### Scenario: Managed package missing

- **WHEN** managed state names a change with no active or archived package
- **THEN** admission fails before writing any admission record or mutating labels, even if a digest can be computed

#### Scenario: Valid managed proof

- **WHEN** the managed task state and exact task-content proof are valid at the admitted head
- **THEN** admission binds the task-content digest and only the archived-verification evidence that is readable and successful

#### Scenario: Malformed archived verification evidence

- **WHEN** the archived automated-checks evidence of a managed task is unreadable or malformed
- **THEN** admission fails explicitly instead of continuing without the gate

#### Scenario: Genuine quick task

- **WHEN** the candidate has no managed task state and its head touches no OpenSpec change
- **THEN** the existing quick-task exact-head identity applies without disguising a managed proof failure
