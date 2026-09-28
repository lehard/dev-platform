# code-erosion-signal Specification

## Purpose
Give reviewers an early, non-blocking signal of gradual code-quality erosion in Dev Platform pull requests by reusing the upstream SlopCodeBench tool.

## Requirements

### Requirement: Pull requests receive an informational code erosion report

Dev Platform SHALL run an independent workflow on pull requests that executes the upstream `scb-check` tool over the shipped Python source areas and publishes a report of erosion, verbosity and cognitive-complexity signals with concrete complexity hotspots. Findings, a non-zero tool exit code, or a report/comment failure SHALL NOT fail the workflow or block merge, and the workflow SHALL NOT be a required check or alter publication and merge policy.

#### Scenario: Tool reports findings

- **WHEN** `scb-check` exits non-zero because it found slop
- **THEN** the workflow still succeeds and publishes the report

#### Scenario: Report is unparseable

- **WHEN** the tool output is missing or garbled
- **THEN** the report states that no parseable result was produced and the workflow still succeeds

### Requirement: The report is deduplicated and always reachable

The report SHALL carry a stable marker so repeated pushes to one pull request update a single comment rather than adding new ones. The report SHALL always be written to the CI job summary, so it remains available when a comment cannot be posted.

#### Scenario: Repeated push

- **GIVEN** a PR already has a marked report comment
- **WHEN** a new commit is pushed
- **THEN** the existing comment is updated and no second report comment exists

#### Scenario: Read-only token

- **WHEN** the token cannot write PR comments
- **THEN** a warning is emitted and the report is available in the job summary

### Requirement: External tools are exactly pinned

The `scb-check` version SHALL be recorded as an exact version in one repository-owned file, and workflow actions SHALL be pinned to commit SHAs. The workflow SHALL NOT use a floating latest tool version; a version change SHALL be an ordinary reviewed change.

#### Scenario: Floating version introduced

- **WHEN** the version file is not an exact `X.Y.Z` release
- **THEN** repository tests fail

### Requirement: The signal is honestly scoped

The report and its documentation SHALL state that the metrics are heuristic, that upstream reference bands are Python-calibrated, and that values are not a universal quality score, SHALL NOT compare values against a blocking threshold, and SHALL NOT duplicate tests, lint or verification. Documentation SHALL record an initial baseline for the scanned areas.

#### Scenario: Non-Python code is added

- **WHEN** a future scanned area contains a non-Python language
- **THEN** the documentation requires its applicability limits to be stated before it is scanned
