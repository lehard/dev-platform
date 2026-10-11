## ADDED Requirements

### Requirement: Every top-level node has a complete editorial explanation and coverage is visible

Every node of the Explorer semantic map at levels 0 to 2 SHALL have a complete Russian editorial explanation for its kind, bound to the canonical sections that support it, and the Explorer SHALL publish a coverage page generated from node data that shows what each level presents, what is deliberately left to engineering sources, and which sources back each node.

#### Scenario: Reader follows an accepted request into work
- **WHEN** a reader starts at the overview and follows the request stage and the Requirement mechanism
- **THEN** the pages explain how an accepted request becomes started work without requiring the reader to open a repository file

#### Scenario: Reader looks up an independent-review finding
- **WHEN** a reader follows the verification stage to the independent-review mechanism
- **THEN** the page explains the repair loop, rejection with rationale and escalation

#### Scenario: Reader looks up delivery to main and to adopted projects
- **WHEN** a reader follows the publication stage and the conditional release stage
- **THEN** the pages explain when a change counts as delivered to main and how a new platform version reaches an adopted project

#### Scenario: Coverage page is built
- **WHEN** the site is built
- **THEN** the coverage page lists every level 0 to 2 node with its kind, level, the stages it participates in and its bound sources, derived from node data
