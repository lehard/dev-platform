## Purpose

Platform-owned task publication is durably observable and safely resumable, so a validated task is not lost when an agent session, terminal stream or authentication candidate fails transiently.

## ADDED Requirements

### Requirement: Sealed automatic publications have durable recoverable state

For `harness_mode=platform`, the platform SHALL create machine-local publication state only after the task branch is committed, lifecycle-valid, and has passed its required local pre-publication checks. The state SHALL identify the branch, immutable candidate commit, configured publication/merge mode, publication phase, PR identity when known, last safe result and actionable next operation; it SHALL contain no credential material. The platform SHALL reject a resume when the candidate commit, branch safety, configuration or lifecycle prerequisites no longer match, and state MAY be deleted because it can be reconstructed from Git and GitHub.

#### Scenario: Interrupted automatic publication resumes the same candidate

- **GIVEN** a sealed branch in `publish_mode=pr` and `pr_merge_mode=auto` has been pushed or has an open PR
- **AND** publication stopped before the PR was merged
- **WHEN** a supported resume operation runs with unchanged safe prerequisites
- **THEN** it resumes that branch and PR from the recorded phase
- **AND** it does not create a second PR or publish a different commit

#### Scenario: Candidate changes after sealing

- **GIVEN** a publication state records candidate commit A
- **WHEN** the task branch no longer resolves to commit A
- **THEN** automatic resume refuses publication
- **AND** reports that the task must be revalidated and sealed again

### Requirement: Automatic publication is single-flight and observable

The platform SHALL ensure that only one automatic publisher controls a sealed candidate at a time. It SHALL emit concise phase transitions and preserve a machine-readable terminal or recoverable status so a disconnected command stream can be distinguished from a failed or still-running publisher.

#### Scenario: A second publisher starts while one is active

- **GIVEN** an active publisher lease for a sealed candidate is still valid
- **WHEN** another finish or resume operation targets that candidate
- **THEN** it does not start a competing publication
- **AND** it reports the existing status and how to inspect or resume it safely

#### Scenario: Publisher command output is disconnected

- **GIVEN** publication has reached a recorded remote phase
- **WHEN** the caller loses the command output stream
- **THEN** a later status or resume operation reports whether the publisher is running, waiting for checks, failed, or completed

### Requirement: Credential candidates are isolated and safe

GitHub CLI/API preflight SHALL validate configured environment-token, local CLI-session and credential-helper candidates independently. An invalid environment token SHALL not prevent a valid lower-precedence local session from being used; credentials and token values SHALL never appear in publication state, logs or diagnostics.

#### Scenario: Exported token is invalid but local GitHub session is valid

- **GIVEN** an exported GitHub token fails authentication
- **AND** the local GitHub CLI session authenticates successfully without that token
- **WHEN** platform publication preflight runs
- **THEN** it uses the authenticated local session
- **AND** continues without exposing either token value

#### Scenario: No credential candidate authenticates

- **WHEN** all supported credential candidates fail authentication
- **THEN** publication remains recoverable and unmerged
- **AND** reports an actionable authentication failure without mutating local main

### Requirement: Browser-QA unavailability is determined after supported discovery

Platform guidance and diagnostics SHALL require a supported local-browser discovery attempt before reporting Playwright browser QA as unavailable. The discovery MAY use a locally installed compatible browser or a compatible cached Playwright browser and SHALL record the actual executable source without prescribing host-specific paths.

#### Scenario: Managed Playwright download is unsupported on the host

- **GIVEN** Playwright cannot download its bundled browser for the current host
- **AND** a compatible local browser executable is available
- **WHEN** an agent performs browser QA
- **THEN** it runs the browser check with that executable
- **AND** does not report browser QA as unavailable solely because the download failed
