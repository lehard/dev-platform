## ADDED Requirements

### Requirement: Routed friction issues remain eligible for periodic process review

Every process-friction issue created or updated by the platform router SHALL carry the configured `process` label and SHALL remain discoverable by the periodic process review while open.

#### Scenario: Router creates a new source issue

- **WHEN** a sanitized friction event is routed to a new GitHub issue
- **THEN** the issue is created with the configured `process` label
- **AND** the routing result verifies that the issue is eligible for the weekly source query

#### Scenario: Existing generated issue lacks the label

- **GIVEN** an unambiguously platform-generated open process-friction issue lacks `process`
- **WHEN** bounded reconciliation runs
- **THEN** the label is restored idempotently
- **AND** unrelated issues are not relabeled

### Requirement: Process-friction duplicate discovery is not limited to one issue page or one free-form slug

The router SHALL search the complete bounded/paginated open source set required by its dedupe contract and SHALL provide a bounded duplicate-candidate path when a new event appears to describe an existing root cause under a different category wording.

#### Scenario: Matching issue is beyond the first API page

- **GIVEN** more open issues exist than fit in one GitHub API page
- **AND** the matching open friction issue is on a later page
- **WHEN** the same fingerprint is routed
- **THEN** the existing issue is updated
- **AND** a duplicate is not created because of pagination

#### Scenario: Category wording changes for the same root cause

- **WHEN** a new event uses a different category slug but materially matches an existing root-cause candidate
- **THEN** the routing flow surfaces the bounded existing candidate before creating a distinct issue
- **AND** it does not perform an unsupported opaque semantic merge
