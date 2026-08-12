## MODIFIED Requirements

### Requirement: Local affected validation never replaces protected PR authority

The platform SHALL distinguish a conservative `local affected` feedback policy from a `protected full` merge-authority policy. For changed paths with a maintained, tested and unambiguous dependency mapping, local affected validation SHALL be able to select canonical bounded test/check groups rather than requiring the complete unit suite solely because the path belongs to a broad language or directory class. A protected-main PR SHALL still require the complete authoritative platform validation set even when a local affected subset has succeeded.

#### Scenario: Proven local affected change

- **WHEN** every changed path is covered by maintained and tested mappings to bounded canonical test/check groups
- **THEN** local feedback executes those mapped groups without unrelated full-suite work
- **AND** a group selected by multiple changed paths is executed only once within the validation invocation
- **AND** the resulting success is not accepted as the protected PR required validation result

#### Scenario: Local path is unknown or high impact

- **WHEN** a changed path is unknown, ambiguously classified, or affects selector/check configuration, CI workflow, OpenSpec/lifecycle control-plane code or another explicitly high-impact surface
- **THEN** local affected validation selects the full authoritative set
- **AND** reports that the fallback was safety-driven

#### Scenario: Protected-main PR is evaluated

- **WHEN** a protected-main PR contains any platform change
- **THEN** CI executes every mandatory validation group in the complete authoritative validation set for the current head
- **AND** merge authority does not depend on a prior local affected run

### Requirement: Parallel validation preserves resource isolation and aggregate authority

The platform SHALL run validation groups concurrently only when each group's mutable resources are isolated per run/worker or the group is explicitly serialized. Independent validation invocations in separate task worktrees SHALL NOT interfere through fixed temporary paths, shared artifacts, locks, ports, process-global state or other mutable test resources. When CI uses partitions, it SHALL publish a stable aggregate required result that fails if any mandatory partition fails.

#### Scenario: Two task worktrees validate concurrently

- **GIVEN** two independent task worktrees execute supported validation at the same time
- **WHEN** their isolation-safe groups use mutable test resources
- **THEN** those resources are namespaced or otherwise isolated per run/worker
- **AND** neither run corrupts, blocks or changes the outcome of the other because of shared fixture state

#### Scenario: Candidate partition shares mutable state

- **WHEN** the resource audit identifies a shared mutable database, artifact path, lock, port, external state, or process-global setting
- **THEN** the candidate is serialized or given proven per-worker isolation before concurrent execution is enabled

#### Scenario: Candidate group has a legitimate shared boundary

- **WHEN** the resource audit identifies mutable state that cannot safely be isolated in this change
- **THEN** that group is explicitly serialized or otherwise bounded
- **AND** unrelated isolation-safe groups are not forced into repository-wide serialization solely because of that boundary

#### Scenario: Partitioned required validation fails

- **WHEN** any mandatory validation partition fails
- **THEN** the stable aggregate required result reports failure
- **AND** protected-main merge remains blocked

## ADDED Requirements

### Requirement: Validation optimization preserves mandatory coverage and proves performance improvement

When the platform changes test execution structure for performance, it SHALL retain comparable before/after evidence for the same mandatory protected coverage. The optimized full path SHALL demonstrate lower wall-clock execution in a repeatable comparable environment before the change is accepted; performance SHALL NOT be improved by silently omitting mandatory tests or replacing current-head validation with a cached/prior result.

#### Scenario: Faster full validation is proposed

- **WHEN** an optimized protected-full execution model is evaluated
- **THEN** before/after evidence identifies the same mandatory test/check coverage and comparable environment
- **AND** the optimized execution demonstrates lower wall-clock duration
- **AND** any remaining serial boundaries and contention effects are recorded

#### Scenario: Proposed speedup reduces coverage

- **WHEN** a proposed optimization obtains lower wall-clock time by omitting a mandatory test/check or by reusing validation from a different head
- **THEN** the optimization is rejected as satisfying neither protected-full authority nor this performance requirement

### Requirement: Validation depth is proportional to a declared risk class

The platform SHALL classify a changed path into one of a small canonical set of risk classes rather than selecting validation depth solely by file-type or directory glob. A documentation/instruction surface with no intended agent-behavior change SHALL receive bounded structure/link/anchor/render checks and SHALL NOT by itself trigger the full mandatory software suite. An executable/harness/control-plane surface, or any path that cannot be confidently classified, SHALL continue to select mapped or full validation as already required.

#### Scenario: Semantic-preserving documentation or instruction change

- **WHEN** every changed path is a documentation/instruction surface (for example `AGENTS.md`, `docs/**`, OpenSpec prose, `template/AGENTS.md.jinja`) and none carries an instruction-behavior-change declaration
- **THEN** local and protected validation execute the bounded documentation/instruction check group instead of the full Python suite
- **AND** that check group still fails on a broken required anchor, a broken link/destination, or a template render defect

#### Scenario: Ambiguous or unrecognized instruction surface

- **WHEN** a changed instruction/documentation-adjacent path does not match a maintained documentation/instruction surface mapping
- **THEN** validation selects the full authoritative set for that path
- **AND** reports that the fallback was safety-driven

### Requirement: Intended agent-behavior change requires executed targeted evidence

A change to an instruction/prompt surface that is declared to intentionally change agent behavior SHALL require the configured targeted behavioral smoke command(s) for the affected runtime/provider to actually execute and succeed as part of that validation invocation. A model's own narrative report that the change is safe SHALL NOT be accepted as behavioral evidence.

#### Scenario: Declared behavior change with executed evidence

- **WHEN** an instruction/prompt surface change is declared as an intended agent-behavior change for a specific runtime/provider
- **AND** the configured targeted behavioral smoke command for that runtime/provider is executed as part of the same validation invocation
- **THEN** the recorded command outcome is required to be successful before the change is accepted as validated for that risk class

#### Scenario: Declared behavior change without executed evidence

- **WHEN** an instruction/prompt surface change is declared as an intended agent-behavior change
- **AND** no configured targeted behavioral command for the affected runtime/provider was executed, or the model's own summary is offered in place of an executed command outcome
- **THEN** the selection falls back to the full authoritative validation set
- **AND** reports that the fallback was evidence-driven
