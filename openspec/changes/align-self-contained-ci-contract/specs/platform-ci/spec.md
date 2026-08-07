## MODIFIED Requirements

### Requirement: Generated guidance matches self-contained CI behavior
Generated documentation SHALL state that downstream platform CI runs from Copier-managed local files and SHALL NOT instruct agents that CI executes a pinned private reusable workflow.

#### Scenario: agent reads platform release guidance
- **WHEN** a downstream repository is generated or updated
- **THEN** its guidance describes reviewed Copier updates as the CI propagation mechanism and identifies `platform_ci_ref` only as legacy compatibility metadata
