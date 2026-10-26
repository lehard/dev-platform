## ADDED Requirements

### Requirement: Selected checks run once per task content

An evidence-producing `select_checks.py --execute` (a managed run with `--evidence`, or a quick run with `--task-evidence`) SHALL refuse before the affected-test precheck and before any selected command starts when the evidence already recorded at that path is reusable for the current task content by the rule finish uses (`check_evidence_reuse`). The refusal SHALL name the evidence path and state that archive and finish reuse it. When existing evidence is not reusable, the run SHALL print the named reason and proceed. Portable `archive` SHALL decide by the same rule before running the selected checks: reusable evidence SHALL be reused and the decision printed, and otherwise the selected checks SHALL run as before. A git or selection failure while deciding SHALL stop explicitly.

#### Scenario: Repeated managed run over unchanged content

- **GIVEN** a managed task whose `automated-checks.json` records a successful run covering the current required selection for unchanged task content
- **WHEN** `select_checks.py --execute --evidence openspec/changes/<change>/automated-checks.json` runs again
- **THEN** it exits non-zero before any selected command starts
- **AND** the message names the evidence and says archive and finish reuse it

#### Scenario: Repeated quick run over unchanged content

- **GIVEN** a quick task whose machine-local evidence is reusable for its current content
- **WHEN** `select_checks.py --execute --task-evidence` runs again
- **THEN** it exits non-zero before any selected command starts, naming the evidence

#### Scenario: Content changed since the evidence

- **WHEN** the task content differs from the content the existing evidence proves, or the evidence failed
- **THEN** the run prints why the evidence is not reusable and executes the selected checks

#### Scenario: Archive after a green evidence run

- **GIVEN** a managed task in a `portable` project whose `select_checks --execute --evidence` run succeeded and whose content did not change afterwards
- **WHEN** archive runs
- **THEN** archive prints that the evidence was reused and executes no selected command
- **AND** finish reuses the same evidence, so the checks run once over evidence, archive and finish

#### Scenario: Archive without reusable evidence

- **WHEN** archive runs with no evidence or with evidence that is not reusable
- **THEN** archive prints the reason and runs the selected checks with evidence as before

### Requirement: Private-reference guard precedes selected-check runs

For checkouts with private lineage enabled, `select_checks.py --execute` SHALL run the existing current-candidate private-reference guard before the affected-test precheck and before any selected command. A missing configured guard or a failed guard SHALL stop explicitly with the guard's non-disclosing diagnostics. Checkouts without private lineage enabled SHALL keep their existing behavior.

#### Scenario: Private reference before a full run

- **GIVEN** a privacy-enabled checkout whose candidate contains a supported private Issue reference
- **WHEN** `select_checks.py --execute` runs
- **THEN** it exits non-zero before any selected command starts with the guard's diagnostic

#### Scenario: Clean or opted-out checkout

- **WHEN** the guard passes or private lineage is disabled
- **THEN** the existing gates and selected commands run unchanged
