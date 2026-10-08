# lifecycle-workers Specification

## Purpose
Let replaceable workers on any placement claim head-bound lifecycle jobs through one contract, while LLM processes hold no publication or repository credential and a deterministic harness performs the only validated, expected-head push.

## Requirements

### Requirement: Lifecycle work is published as head-bound jobs

The coordinator SHALL publish review, repair, integration-repair, finalize, retrospective, terminal-reconciliation and cleanup work as jobs bound to an exact candidate head, task-content identity and attempt. A job result for a different head SHALL be discarded.

#### Scenario: Candidate head moves while a job runs
- **WHEN** a worker returns a result for an older head
- **THEN** the result is discarded and the job is re-evaluated for the current head

### Requirement: Replaceable workers claim jobs through one contract

Workers SHALL claim jobs through one work-next contract with a head-bound, time-limited claim. At most one valid claim SHALL own a job; an expired or head-stale claim SHALL be reclaimable. Local, remote and hybrid placement SHALL differ only in where workers run and which job kinds they advertise.

#### Scenario: Two workers race
- **WHEN** two workers claim the same job
- **THEN** exactly one proceeds and the other abandons without side effects

#### Scenario: Worker dies
- **WHEN** a claim expires without a result
- **THEN** another worker can claim the job

### Requirement: LLM workers hold no publication or repository credential

An LLM process executing review, repair or integration-repair SHALL run without any GitHub, publication or repository credential and SHALL NOT have merge authority. Review SHALL be read-only. Any write result SHALL be validated by a deterministic harness — fast-forward from the expected head, within the candidate's scope, without workflow or lifecycle-evidence edits — and the harness SHALL perform the only push to that candidate branch with an expected-head guard.

#### Scenario: Repair touches a workflow file
- **WHEN** a repair result modifies a CI workflow or another candidate's paths
- **THEN** the harness rejects it and nothing is pushed

#### Scenario: Credential discovery attempt
- **WHEN** the LLM process inspects its environment
- **THEN** no GitHub token, credential helper or SSH agent is available

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
