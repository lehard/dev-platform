# platform-lifecycle Specification Delta

## ADDED Requirements

### Requirement: Shared Requirement PR publication does not claim one child

A protected publisher handling a candidate with multiple verified internal children SHALL use an exact committed Requirement manifest as its identity and SHALL NOT infer one child for its pre-merge Project update. Required PR checks and exact merged-PR terminal reconciliation remain mandatory.

#### Scenario: Valid combined candidate

- **GIVEN** a clean candidate with a committed manifest linking multiple children to one Requirement
- **WHEN** the shared publisher opens or resumes its exact-head PR
- **THEN** it does not assign the PR to one child Issue
- **AND** the parent remains nonterminal until protected merge is confirmed

#### Scenario: Shared identity is missing or ambiguous

- **GIVEN** an absent, uncommitted, malformed or unlinked shared manifest
- **WHEN** the shared publication mode is requested
- **THEN** publication stops before push or PR mutation
