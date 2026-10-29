## ADDED Requirements

### Requirement: The overview shows agent sessions beside the work they belong to

`lifecycle_overview.py` SHALL read the platform session registry and show each live session with its status next to the candidate whose PR head ref equals the session's branch, including a developer session after handoff, and list the remaining sessions separately. If the registry is not configured or cannot be read, the overview SHALL say so explicitly and SHALL NOT present sessions as absent.

#### Scenario: Developer session after handoff
- **GIVEN** a session on branch `agent/br-1-t1-x` and an open PR with that head ref
- **WHEN** the overview renders the candidate
- **THEN** the session and its status appear on that candidate

#### Scenario: Registry not configured
- **WHEN** no session registry directory is configured
- **THEN** the overview states that session status is not configured
