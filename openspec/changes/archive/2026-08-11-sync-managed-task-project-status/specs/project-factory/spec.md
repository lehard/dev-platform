## ADDED Requirements

### Requirement: Generated managed repositories can address Development Backlog workflow state

A repository participating in managed-task execution SHALL carry validated
configuration sufficient to resolve the intended Development Backlog GitHub
Project and its workflow `Status` field through supported authenticated GitHub
interfaces. The configuration SHALL use a stable Project locator and SHALL NOT
depend on UI scraping or a mutable display title alone.

#### Scenario: Managed repository receives Project-status support

- **WHEN** the platform release containing status synchronization is rendered or applied
- **THEN** the repository has the self-contained helper/runtime and reviewed configuration needed to resolve its managed Issue Project item
- **AND** the expected workflow options include `Backlog`, `Ready`, `In progress`, `In review`, `Blocked`, and `Done`

#### Scenario: Project workflow configuration is unavailable

- **WHEN** a managed execution requires status synchronization but the Project locator, field mapping or mutation permission is missing/invalid
- **THEN** platform validation/lifecycle reports an actionable setup failure
- **AND** it does not silently claim that central workflow state is synchronized

### Requirement: Project-status synchronization preserves execution-plane boundaries

The Project Factory SHALL keep Development Backlog workflow projection separate
from machine-local multi-agent coordination and from quick tasks without a
managed source Issue.

#### Scenario: Multi-agent task starts

- **WHEN** a managed multi-agent task is claimed
- **THEN** the local board continues to own worktree/scope coordination
- **AND** Development Backlog `Status` represents the human lifecycle stage rather than mirroring local board records

#### Scenario: Quick task runs

- **WHEN** an immediate quick task has no managed Development Backlog source
- **THEN** the Project-status helper performs no central workflow mutation solely because local task execution occurs
