## ADDED Requirements

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
