## ADDED Requirements

### Requirement: GitHub-aware task lifecycle
The platform SHALL fetch and compare the configured remote integration branch before starting work and again immediately before publication. It SHALL abort rather than auto-resolve divergent histories and SHALL never force-push.

#### Scenario: remote main advances before start
- **WHEN** local main is clean and behind origin/main
- **THEN** the platform fast-forwards local main before creating task work

#### Scenario: remote main diverges before publication
- **WHEN** local and remote integration history are not in a safe ancestor relationship
- **THEN** publication aborts and requires explicit reconciliation

### Requirement: Configurable publication modes
The platform SHALL support `pr` and `direct` publication modes. PR mode SHALL publish a feature branch and create/reuse a GitHub PR without auto-merging it. Direct mode SHALL publish only a safe fast-forward of the integration branch.

### Requirement: Composable workflow profiles
The platform SHALL provide `light`, `standard`, and `multi-agent` profiles from one template. Worktrees and the agent board SHALL only be mandatory for `multi-agent`.

### Requirement: OpenSpec contract coherence
For non-trivial OpenSpec work, agents SHALL update planning artifacts before knowingly implementing a changed intent, observable behavior, technical design, or execution plan. Non-trivial changes SHALL undergo project-specific verification and `/opsx:verify` before archive.

### Requirement: Versioned platform dependency
Generated downstream CI SHALL reference a versioned platform release ref or immutable SHA and SHALL NOT reference `dev-platform@main`.

### Requirement: Deliberate learning promotion
Platform friction SHALL remain local unless explicitly promoted. Promotion SHALL omit raw evidence by default, sanitize obvious credential-like content, and require an explicit authenticated action.
