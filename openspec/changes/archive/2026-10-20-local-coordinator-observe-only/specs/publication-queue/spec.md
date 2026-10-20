## ADDED Requirements

### Requirement: Local coordinator run is observe-only

Only the CI `publication-queue` workflow, acting as the coordinator GitHub App, SHALL integrate or merge candidates into `main`. `publication_queue.py worker --mode local` SHALL NOT observe, prepare, integrate or merge any candidate: it SHALL exit non-zero before any GitHub read with a diagnostic that names the CI coordinator as the only integrator and points to `publication_queue.py status` and `publication_queue.py preflight --mode local`. `status` and `preflight --mode local` SHALL work without an App token. The local preflight SHALL NOT require repository push permission.

#### Scenario: Local run does not integrate

- **WHEN** an operator runs `publication_queue.py worker --mode local`
- **THEN** it exits non-zero naming the CI coordinator and the `status` and `preflight --mode local` commands
- **AND** no pull request, comment, label or branch is read, written or merged

#### Scenario: Local diagnostics without App token

- **GIVEN** a local `gh` login without any App token
- **WHEN** an operator runs `status` or `preflight --mode local`
- **THEN** both commands complete
- **AND** the local preflight does not probe or require repository push permission
