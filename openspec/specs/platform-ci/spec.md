# Platform CI

## Requirements

### Requirement: Downstream CI has no private repository access prerequisite
Generated project CI SHALL execute platform-managed check scripts from the checked-out downstream repository and SHALL NOT require access to a private reusable workflow in `dev-platform`.

#### Scenario: private project adopts the platform
- **WHEN** the project runs its generated CI without any cross-repository Actions Access setting
- **THEN** GitHub executes the platform-managed checks from local Copier-managed files

### Requirement: CI updates remain reviewed and versioned
The downstream CI workflow and check scripts SHALL remain Copier-managed project files so platform changes arrive through reviewed template updates rather than mutable remote execution.

### Requirement: Generated guidance matches self-contained CI behavior
Generated documentation SHALL state that downstream platform CI runs from Copier-managed local files and SHALL NOT instruct agents that CI executes a pinned private reusable workflow.

#### Scenario: agent reads platform release guidance
- **WHEN** a downstream repository is generated or updated
- **THEN** its guidance describes reviewed Copier updates as the CI propagation mechanism and identifies `platform_ci_ref` only as legacy compatibility metadata
