## ADDED Requirements

### Requirement: Dev Platform can produce read-only architecture health evidence

Dev Platform SHALL support an advisory architecture review bound to an exact repository revision that reports bounded evidence about module/interface boundaries, locality, coupling, seams and related structural risks without modifying repository or managed-task state.

#### Scenario: Architecture review runs
- **WHEN** an architecture health review is requested for a repository revision
- **THEN** the result identifies the exact revision and evidence-bearing code locations
- **AND** separates observations from uncertainty and proposed improvements
- **AND** performs no repository or backlog mutation

### Requirement: Architecture findings require explicit human promotion

Architecture health findings SHALL remain advisory until a human explicitly accepts a candidate as managed work through the normal task-intake lifecycle.

#### Scenario: Review finds a refactor candidate
- **WHEN** the report identifies a potentially valuable architectural improvement
- **THEN** it does not create a managed task or change code automatically
- **AND** any later accepted work is authored separately through the ordinary managed lifecycle

### Requirement: Alternative design analysis is selective

Dev Platform SHALL permit bounded comparison of materially different design/interface alternatives for high-consequence architecture decisions without requiring that ceremony for ordinary changes.

#### Scenario: Significant interface decision is reviewed
- **WHEN** an explicitly configured architecture trigger requests alternative-design analysis
- **THEN** at least two materially distinct designs can be compared against stated criteria
- **AND** the comparison remains evidence for the existing OpenSpec design decision rather than a competing specification source
