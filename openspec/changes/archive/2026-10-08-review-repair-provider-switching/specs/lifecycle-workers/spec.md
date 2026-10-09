## ADDED Requirements

### Requirement: Workers select jobs by PR and by preflight-proven provider

A worker SHALL be able to restrict job selection to given PRs and to review and repair providers whose runtime passed a bounded readiness probe in the worker's own scratch environment, using the same login files the job would use. A job whose providers include no ready provider of the worker SHALL be skipped without a claim and SHALL NOT block jobs of other providers. A job carrying no resolved provider SHALL NOT be eligible for a provider-filtering worker. Unready providers and their limitations SHALL be reported. A worker that runs a repair job SHALL declare the provider of its writer command and SHALL fail explicitly when it does not. Without these options selection SHALL be unchanged.

#### Scenario: Unrunnable job at the lowest PR
- **GIVEN** the lowest-numbered claimable job names only a provider that fails preflight on this worker
- **AND** a higher-numbered job names a ready provider
- **WHEN** the worker selects with provider filtering
- **THEN** it claims the higher-numbered job and places no claim on the first

#### Scenario: Selection by PR
- **WHEN** the worker selects with a PR filter
- **THEN** only jobs of those PRs are considered

#### Scenario: Review uses the ready subset in job order
- **GIVEN** a review job names providers claude then codex and only codex is ready
- **WHEN** the worker runs it
- **THEN** the review runs on codex alone

#### Scenario: Repair without a declared provider
- **WHEN** a worker runs a repair job without declaring its writer provider
- **THEN** it fails explicitly before claiming

### Requirement: An unavailable writer runtime is not a failed repair

When a repair writer exits unsuccessfully or cannot start, the worker SHALL decide whether its provider runtime is usable with the same readiness probe. An unusable runtime SHALL be reported as unavailable with its limitation and SHALL NOT complete the job; a usable runtime SHALL keep the failure a real failed result.

#### Scenario: Writer cannot start
- **WHEN** the writer command cannot be executed
- **THEN** the outcome is unavailable naming the start failure and the job remains claimable
