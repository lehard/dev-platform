## ADDED Requirements

### Requirement: Managed selected-check runs refuse observable blockers before any command

`select_checks.py --execute` in a registered managed task checkout whose change is still active (`openspec/changes/<change>/` exists) SHALL refuse, before the affected-test precheck and before any selected command starts, when the run cannot produce usable handoff evidence: when no `--evidence` path is given, or when the managed change is not archive-ready (incomplete or missing `tasks.md` checkboxes, or a new-capability delta without an authored `## Purpose`). The refusal SHALL name the blocker and the next action. In the platform's full validation set, the cheap generated-manifest check SHALL run before the full test run.

#### Scenario: Managed run without evidence

- **GIVEN** a registered managed task checkout
- **WHEN** `select_checks.py --execute` runs without `--evidence`
- **THEN** it exits non-zero before any selected command starts
- **AND** the message names `--evidence openspec/changes/<change>/automated-checks.json`

#### Scenario: Last task checkbox still open

- **GIVEN** a registered managed task whose `tasks.md` has an unchecked item
- **WHEN** `select_checks.py --execute --evidence ...` runs
- **THEN** it exits non-zero before any selected command starts
- **AND** the message names the incomplete task count, so ticking the box happens before the only full run

#### Scenario: Archive-ready managed run proceeds

- **GIVEN** a registered managed task with evidence requested and all tasks complete
- **WHEN** `select_checks.py --execute --evidence ...` runs
- **THEN** the existing freshness and scope gates and the selected commands run unchanged

#### Scenario: Archived managed change keeps the existing path

- **GIVEN** a registered managed task whose change is already archived
- **WHEN** a completion command runs `select_checks.py --execute` without `--evidence`
- **THEN** neither refusal applies and validation runs as before

#### Scenario: Stale generated manifest

- **GIVEN** the generated platform manifest no longer matches the sources
- **WHEN** the platform's full validation set runs
- **THEN** the manifest check fails before `run_test_groups.py --all` starts
