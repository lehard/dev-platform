## ADDED Requirements

### Requirement: Explorer presents an ordered end-to-end lifecycle journey

The Explorer SHALL present the Dev Platform lifecycle as an ordered sequence of stages from requirement or intent through specification, routing and execution, verification, publication and integration, release and rollout, to feedback. Each stage SHALL link to the component elements and canonical sources it is explained by, and its explanation SHALL be rendered from those sources rather than stored in the Explorer map.

#### Scenario: Reader follows the lifecycle
- **WHEN** a reader opens the lifecycle overview
- **THEN** every declared stage is shown in order with a stable link
- **AND** each stage page offers previous and next stage navigation and links to its related component elements

#### Scenario: Component page shows lifecycle usage
- **WHEN** a component element is involved in one or more stages
- **THEN** its page lists those stages with links

#### Scenario: Stage definition is invalid
- **WHEN** a stage has a duplicate or non-contiguous order, references a missing element, or references an unresolved source
- **THEN** the build fails non-zero naming the stage and writes no output

#### Scenario: Lifecycle pages without scripting
- **WHEN** the lifecycle pages are opened without JavaScript or under a path prefix
- **THEN** the flow, stage content and navigation remain usable
