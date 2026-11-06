# chat-coordinator Specification

## Purpose
Let the owner assign any new Codex or Claude session as the chat coordinator, which keeps the roadmap, runs the one development stream and tells the owner where work stands from GitHub and machine-local registries alone, without a persistent chat, a second state store or a new step on the happy path.

## Requirements

### Requirement: The platform runs one stream with one writer

The platform SHALL run one development stream with one writer at a time. The coordinator SHALL NOT start a second writing stream, and no platform mechanism SHALL rely on parallel writers.

#### Scenario: A second writing task is proposed
- **WHEN** a writing task is proposed while another stream is open
- **THEN** it waits until the open stream has merged or been abandoned

### Requirement: Lifecycle overview is a read-only projection

The platform SHALL provide a read-only overview that shows open Requirements of the project with their progress and pending owner acceptance, open owner-needed signals and live agent sessions, and a drill-down for one Requirement.

#### Scenario: Cold session asks for the state of all work
- **WHEN** the overview is run from a fresh checkout
- **THEN** it lists every open Requirement of this project with its stage and status
- **AND** it performs no GitHub write

#### Scenario: A source cannot be read
- **WHEN** Requirement progress or operator acceptance cannot be read
- **THEN** the overview reports that item as `unknown` with the reason and never presents it as healthy

### Requirement: The overview shows agent sessions

`lifecycle_overview.py` SHALL read the platform session registry and list each live session with its status, branch and project. If the registry is not configured or cannot be read, the overview SHALL say so explicitly and SHALL NOT present sessions as absent.

#### Scenario: The registry is unreadable
- **WHEN** the session registry cannot be read
- **THEN** the overview prints that it is unreadable and why

### Requirement: The lifecycle overview shows open owner-needed signals

The overview SHALL list open owner-needed signals exactly as `agent_signal` stores them, and SHALL say so explicitly when the agent board capability is off or the board cannot be read.

#### Scenario: An owner signal is open
- **WHEN** an agent left an open owner-needed signal
- **THEN** the overview shows its project, task, question, id and age

### Requirement: The lifecycle overview read cache is disposable

GitHub reads of the overview MAY go through a local ETag read cache. Deleting the cache SHALL NOT change any result, and a corrupt cache SHALL fail explicitly, naming the file.

#### Scenario: The cache is corrupt
- **WHEN** a cache file cannot be parsed
- **THEN** the overview fails naming the file and reports no partial state

### Requirement: Final Requirement closure keeps the existing Requirement Issue close

The coordinator SHALL close a Requirement only through `requirement_terminal.py`, which keeps its terminal checks and operator acceptance.

#### Scenario: A delivered Requirement needs recovery
- **WHEN** a delivered Requirement stayed open
- **THEN** `requirement_terminal.py reconcile` closes it after its checks pass

### Requirement: The chat coordinator keeps the backlog roadmap

The coordinator SHALL keep the order of Requirements taken into work and SHALL state it on request.

#### Scenario: The next task is chosen
- **WHEN** the open stream has merged
- **THEN** the coordinator picks the next task from the roadmap

### Requirement: The chat coordinator writes no code

The coordinator SHALL NOT perform a stream's task and SHALL NOT write product or platform code itself.

#### Scenario: A stream needs code
- **WHEN** a task needs code
- **THEN** the coordinator starts the one stream to do it

### Requirement: Material and business decisions remain the owner's

The coordinator SHALL bring material findings, business decisions and OpenSpec contract conflicts to the owner with options, their cost or risk and a recommendation.

#### Scenario: A contract conflict appears
- **WHEN** a material product-contract conflict appears
- **THEN** the coordinator presents options and a recommendation and waits for the owner

### Requirement: The chat coordinator states facts only from observed sources

The coordinator SHALL state delivery facts only from the overview, GitHub or the repository, and SHALL keep unknown things unknown.

#### Scenario: A state is not observable
- **WHEN** a state cannot be read
- **THEN** the coordinator reports it as unknown

### Requirement: The chat coordinator bypasses no protection and touches no other agent's state

The coordinator SHALL NOT bypass a required check or branch protection, and SHALL NOT change another agent's worktree, branch or scope.

#### Scenario: A required check is red
- **WHEN** a required check fails on the exact head
- **THEN** the PR does not merge and the stream repairs it

### Requirement: The chat coordinator runbook lets a new session reconstruct state

`docs/engineering/chat-coordinator.md` SHALL let a new session reconstruct the delivery state and continue without a prior conversation.

#### Scenario: A new session takes the role
- **WHEN** a new session is assigned as coordinator
- **THEN** it reads the runbook and the overview and continues the roadmap
