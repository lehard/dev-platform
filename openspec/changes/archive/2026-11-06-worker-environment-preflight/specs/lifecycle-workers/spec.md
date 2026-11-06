## ADDED Requirements

### Requirement: A worker proves its environment before the first claim

Before its first claim and first GitHub write, `work-next --run` SHALL evaluate every environment condition of the requested job kinds and, when any is unmet, SHALL exit non-zero naming all unmet conditions and place no claim. A job-dependent condition SHALL run after selection and before claim. An unevaluable condition SHALL refuse, and a standalone command SHALL run the same conditions without a job.

#### Scenario: Several conditions unmet

- **GIVEN** a worker with no `gh` credential and no valid Claude credential
- **WHEN** it runs `work-next --kinds review --provider claude --run`
- **THEN** it exits non-zero naming both conditions and no claim is posted

#### Scenario: Selected job names an unready provider

- **WHEN** the selected job names only a provider whose readiness fails
- **THEN** the job is reported as refused with the limitation and no claim is posted

#### Scenario: Standalone check

- **WHEN** an operator runs the standalone check for a job kind
- **THEN** every condition of that kind is printed with its state and no job is read or claimed

### Requirement: An environment failure spends no budget of the candidate

A failure of a registered preflight condition after claim SHALL release the claim with an environment class naming the condition, and `work-next` SHALL exit non-zero naming it. It SHALL NOT count toward `MAX_RELEASES` or attempts and SHALL NOT produce a review report or a finalize block. Any other failure SHALL stay an ordinary failed run.

#### Scenario: Credential lost during a review

- **GIVEN** a claimed review
- **WHEN** a registered condition fails during the run
- **THEN** the claim is released with the environment class
- **AND** the release count and attempts of the job are unchanged

#### Scenario: Finalize environment failure

- **WHEN** a registered condition fails during a claimed finalize
- **THEN** the candidate does not become `blocked-escalation` and the job stays claimable

#### Scenario: Candidate defect

- **WHEN** a run fails for a reason outside the registry
- **THEN** it counts as a failed run as before

### Requirement: Repeated environment releases end in an operational block

Environment releases of one job SHALL have their own bound. When it is reached the candidate SHALL enter `blocked-escalation` with an operational cause that names the condition, and candidate attempt counters SHALL NOT change. `resume` SHALL lift it for a review, repair or finalize job; an integration job's escalation is lifted by a developer re-admission, like its other escalations.

#### Scenario: Bound reached

- **WHEN** a job reaches the environment release bound
- **THEN** the overview reports an operational escalation naming the condition
- **AND** `resume` offers a review, repair or finalize job again with its attempts unchanged
