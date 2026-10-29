## ADDED Requirements

### Requirement: Expensive lifecycle commands run one shared preflight of known conditions

`select_checks.py --execute` and `finish_task.py` (first submission, developer handoff and re-submission) SHALL, before the affected-test precheck, any selected command or any other expensive operation, evaluate one ordered registry of cheap conditions in `lifecycle_preflight.py`: shared-workspace permissions on the task paths, the task's board claim and scope together with scope overlap, the task's freshness against authoritative main under the existing behind-mergeable contract, and the project's configured cheap gates (`[settings] preflight_commands`). Each condition SHALL call the function the corresponding gate uses, and SHALL report `passed`, `repaired` or `not-applicable` with the fact that makes it so, or refuse. The command SHALL print every condition checked with its result. When any condition refuses, the command SHALL exit non-zero before the first expensive operation, reporting every refused condition together with the violated condition and the command that repairs it. A condition that cannot be evaluated SHALL refuse; no condition SHALL pass by default.

#### Scenario: Task without a board claim

- **GIVEN** the agent board capability is required and the task's worktree has no claim
- **WHEN** `select_checks.py --execute` runs
- **THEN** it exits non-zero within seconds, before any selected command starts
- **AND** the message names the missing claim and the `agent_board.py` command that registers it

#### Scenario: Project cheap gate fails

- **GIVEN** `preflight_commands` lists the writer-guard baseline test and a new direct file-creation site is not in the baseline
- **WHEN** `select_checks.py --execute` or `finish_task.py` runs
- **THEN** it exits non-zero before the full validation set starts, naming the command and the unregistered site

#### Scenario: Task behind a conflicting main

- **GIVEN** main moved so the task is not behind-mergeable
- **WHEN** a lifecycle command runs the preflight
- **THEN** it refuses before validation with the conflicting files and the `reconcile` command
- **AND** a task that is behind-mergeable passes as it does for the gate today

#### Scenario: Several refusals at once

- **WHEN** two conditions are violated
- **THEN** one error names both, each with its repair command

#### Scenario: Preflight output

- **WHEN** every condition passes or is not applicable
- **THEN** the command prints each condition id with its result and the validation proceeds unchanged

#### Scenario: Not applicable is explicit

- **GIVEN** a disposable checkout declared with `--scope-gate not-applicable`, or a project without `preflight_commands`
- **WHEN** the preflight runs
- **THEN** the affected condition is printed as `not-applicable` with the configuration fact, never silently skipped

#### Scenario: Gate and preflight agree

- **WHEN** the same state is evaluated by a gate function and by its preflight condition
- **THEN** both give the same verdict and the same violated-condition message
