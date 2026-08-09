## MODIFIED Requirements

### Requirement: Downstream CI has no private repository access prerequisite
Generated project CI SHALL execute platform-managed check scripts from the checked-out downstream repository and SHALL NOT require access to a private reusable workflow in `dev-platform`.

#### Scenario: private project adopts the platform
- **WHEN** the project runs its generated CI without any cross-repository Actions Access setting
- **THEN** GitHub SHALL create and execute the platform check job normally

### Requirement: CI updates remain reviewed and versioned
The downstream CI workflow and check scripts SHALL remain Copier-managed project files so platform changes arrive through reviewed template updates rather than mutable remote execution.
