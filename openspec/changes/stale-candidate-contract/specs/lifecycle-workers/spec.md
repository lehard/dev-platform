## ADDED Requirements

### Requirement: A worker job kind fixes its contract source

The contract source of a job SHALL be set by its kind before any contract is read, and the result of a schema check SHALL NOT select it. Review and repair checkouts SHALL always receive the public contract of the worker's trusted revision. A missing trusted contract SHALL fail the job naming the file.

#### Scenario: Stale candidate in review

- **GIVEN** a candidate whose contract lacks a key the worker's schema requires
- **WHEN** a worker runs its review
- **THEN** the review reads the trusted contract and no `PlatformConfigError` arises

#### Scenario: Valid candidate contract in review

- **GIVEN** a candidate whose contract passes the schema
- **WHEN** a worker runs its review
- **THEN** the checkout still receives the trusted contract

### Requirement: An integration harness reads the contract of its merged head

After merging main, an integration job's harness SHALL read the committed public contract of the merged head, never a copy installed at the candidate head. Installation SHALL replace only an untracked installed copy, SHALL leave a committed `.dev-platform.toml` untouched, and SHALL fail naming `dev-platform/source-contract.toml` when the head has neither.

#### Scenario: Stale copy after the merge

- **GIVEN** a harness whose installed copy lacks a key that the merged head's committed contract has
- **WHEN** the harness moves to the merged head
- **THEN** the contract it reads has that key

#### Scenario: Committed project contract

- **GIVEN** a head that commits `.dev-platform.toml`
- **WHEN** the harness moves to that head
- **THEN** the committed file stays as committed

#### Scenario: No contract at the head

- **GIVEN** a head with neither contract
- **WHEN** the harness moves to that head
- **THEN** the job fails naming `dev-platform/source-contract.toml`

### Requirement: Finalize refuses an invalid candidate contract before claim

Finalize, including a composition finalize, SHALL read the candidate contract. When that contract is invalid or unreadable at the exact job head, the job SHALL be refused before claim, naming the key and the exit of reconciling the candidate with main and running `finish`. No attempt or release SHALL be spent, and no other contract SHALL be used.

#### Scenario: Missing required key

- **GIVEN** a `finalize-pending` candidate whose contract lacks a required key
- **WHEN** a worker selects its finalize job
- **THEN** no claim is posted and the refusal names the key and the exit
- **AND** the release count and attempts of the job are unchanged

#### Scenario: Exit taken

- **WHEN** the developer reconciles the candidate with main and runs `finish`
- **THEN** the descendant head is re-admitted and its finalize job can be claimed
