## MODIFIED Requirements

### Requirement: Expensive lifecycle commands run one shared preflight of known conditions

`select_checks.py --execute` and `finish_task.py` (first submission, developer handoff and re-submission) SHALL, before the affected-test precheck, any selected command or any other expensive operation, evaluate one ordered registry of cheap conditions in `lifecycle_preflight.py`: shared-workspace permissions on the task paths, the task's board claim and scope together with scope overlap, the task's freshness against authoritative main under the existing behind-mergeable contract, the project's configured cheap gates (`[settings] preflight_commands`), and whether the task's committed selected-check evidence still proves its content. Each condition SHALL call the function the corresponding gate uses, and SHALL report `passed`, `repaired` or `not-applicable` with the fact that makes it so, or refuse. The command SHALL print every condition checked with its result. When any condition refuses, the command SHALL exit non-zero before the first expensive operation, reporting every refused condition together with the violated condition and the command that repairs it. A condition that cannot be evaluated SHALL refuse; no condition SHALL pass by default.

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

#### Scenario: Committed evidence bound to an old base

- **GIVEN** a managed task whose committed selected-check evidence is a publication gate and whose content proof no longer matches after main moved under the task
- **WHEN** `finish_task.py` runs the preflight
- **THEN** it refuses before validation naming the evidence path and the exact `select_checks.py --base origin/main --execute --evidence <path>` refresh command

## ADDED Requirements

### Requirement: Reconcile reports committed evidence a base move invalidated

After `reconcile` merges authoritative main into a managed task, it SHALL evaluate the task's committed selected-check evidence with the content-proof comparison the evidence gate uses. When that evidence is a publication gate (the change is archived, or the task is a coordinator-managed candidate) and no longer proves the task content, `reconcile` SHALL exit non-zero after the merge, naming the evidence path, its recorded base and the current base, and printing the exact refresh command `python3 scripts/select_checks.py --base origin/main --execute --evidence <path>` followed by committing the refreshed evidence. Evidence that still proves the content SHALL pass unchanged. A quick task's machine-local evidence is not committed: `reconcile` SHALL report that finish reruns validation for it and SHALL NOT fail. Inability to compute the current content proof SHALL fail explicitly.

#### Scenario: Main changed a task path

- **GIVEN** an archived managed change with committed evidence and a main commit that changed a path of the task
- **WHEN** `reconcile` merges that main
- **THEN** it exits non-zero after the merge with the evidence path and the refresh command

#### Scenario: Main changed only unrelated paths

- **GIVEN** committed evidence and a main commit touching no task path
- **WHEN** `reconcile` merges that main
- **THEN** it succeeds and reports no stale evidence

#### Scenario: Active change in the portable lifecycle

- **GIVEN** an active managed change outside the coordinator lifecycle
- **WHEN** `reconcile` or the preflight evaluates its evidence
- **THEN** the condition is not applicable because archive revalidates non-reusable evidence
