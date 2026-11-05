## ADDED Requirements

### Requirement: An abandoned Codex delegation closes on proven evidence

`model_routing.py close-abandoned-delegation --reason TEXT` SHALL close an open Codex delegation with outcome `abandoned` only when no process outside the caller's own ancestry runs in the assigned worktree. It SHALL record the reason, observation and post task content, SHALL create no execution evidence, and SHALL allow a new route afterwards. Any other state SHALL be refused with its reason and next action, writing nothing.

#### Scenario: Supervisor process was killed
- **GIVEN** an open Codex delegation whose process no longer runs
- **WHEN** the command runs with a reason
- **THEN** the delegation is closed as abandoned, no execution is recorded, and a new route can be prepared

#### Scenario: A process still runs in the worktree
- **WHEN** another process has its working directory in the assigned worktree
- **THEN** the command refuses naming the process and writes nothing

#### Scenario: Liveness cannot be observed
- **WHEN** the process observation is unavailable or fails
- **THEN** the command refuses naming the cause and writes nothing

#### Scenario: No open Codex delegation
- **WHEN** the route has no open delegation or it belongs to Claude
- **THEN** the command refuses naming the state and the supported path

### Requirement: route-codex names the writer

`route-codex` output SHALL state who writes task content: the delegated child on R1 and R2, the retained parent on R3.

#### Scenario: R2 route
- **WHEN** `route-codex` runs on R2
- **THEN** its output names the Codex child as the writer and states that the supervisor does not write task content
