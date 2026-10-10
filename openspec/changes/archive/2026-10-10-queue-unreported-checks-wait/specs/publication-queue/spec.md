## MODIFIED Requirements

### Requirement: Exact-head required-check observation

The platform SHALL derive the required-check state of a pull request from valid structured GitHub check output, SHALL resolve the required set from the pull request's final protected target (the main branch for main-targeted pull requests and for Requirement contribution pull requests targeting a `requirement/BR-<n>` integration branch), and SHALL bind the snapshot to the expected PR head both before and after reading the checks. Passed, pending, failed and not-registered observations SHALL remain distinct from unusable observations, which SHALL carry an explicit cause (transport failure, malformed output, head mismatch or unsupported state) and SHALL NOT authorize publication. The no-required-checks condition SHALL be resolved from the base branch's protection, not from CLI wording. A required context that the protected target requires but that is not yet reported on the observed head SHALL be pending (`EXPECTED`), not unusable; the coordinator's integration wait for such checks SHALL be bounded and SHALL end in an explicit block naming the unreported checks. A pending check or a repairable failed check SHALL NOT terminally block a candidate; an unusable observation SHALL be reported with its cause and SHALL NOT be substituted by an assumed state.

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
- **THEN** the observation is derived from the contribution's `validate` check, a missing `validate` row is pending as `EXPECTED`, and the contribution can record a passed required-checks gate once `validate` succeeds

#### Scenario: Contribution preserves required App binding

- **WHEN** main requires a check from a specific App and a contribution has a successful check of the same name from another App
- **THEN** that success does not satisfy the requirement; the required App's missing run remains pending, and only its exact-head run determines the bound check state

#### Scenario: Base branch requires no checks

- **WHEN** gh reports no required checks for a main-targeted pull request and the base branch protection requires no status checks
- **THEN** the observation is not-registered with a detail naming the base branch, decided from branch protection rather than CLI text

#### Scenario: Unusable observation

- **WHEN** gh exits with an unexpected status, its output is not valid JSON, or the PR head differs from the expected head before or after the checks are read
- **THEN** the observation is unusable with a cause of transport, malformed or head-mismatch and cannot authorize publication

#### Scenario: Transport or head fault does not terminally block

- **WHEN** the coordinator receives an unusable observation caused by transport failure or head mismatch while integrating a candidate
- **THEN** it reports a non-terminal waiting result naming the cause and does not mark the candidate blocked

#### Scenario: Required checks not yet reported on a fresh head

- **WHEN** gh reports no required checks for a main-targeted pull request whose base protection requires `validate`, because GitHub has not yet attached any check to the head the coordinator just produced
- **THEN** the observation is pending with an `EXPECTED` `validate` row and a detail naming it, and the coordinator keeps waiting instead of blocking the candidate
- **AND** the candidate integrates once `validate` passes on that head

#### Scenario: Required checks never reported within the bound

- **WHEN** the coordinator's integration check wait expires while every required check of the head is still `EXPECTED`
- **THEN** the candidate is blocked with a reason naming the unreported checks and the bound
- **AND** it is never integrated without passed required checks
