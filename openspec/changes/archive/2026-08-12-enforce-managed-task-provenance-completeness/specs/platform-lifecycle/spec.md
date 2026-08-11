## ADDED Requirements

### Requirement: Managed resume and publication require canonical OpenSpec provenance

For work originating from a Development Backlog managed Issue, platform-owned resume/finish SHALL verify the matching repository-local active or archived OpenSpec provenance before treating the task as a valid managed execution. Publication SHALL also require the existing task-completion, semantic-verification and archive evidence appropriate to the task's lifecycle stage.

#### Scenario: Managed implementation is still active

- **WHEN** a managed task resumes with a matching active canonical OpenSpec change
- **THEN** execution may continue using that change as the implementation contract
- **AND** normal no-silent-divergence rules continue to apply

#### Scenario: Managed PR has code but no matching canonical change

- **WHEN** an existing managed branch or PR has implementation changes but matching active/archived OpenSpec provenance cannot be resolved
- **THEN** the lifecycle blocks further managed publication
- **AND** reports the missing/mismatched source evidence instead of inferring completion from the code or PR alone

#### Scenario: Managed PR directly changes current specs without lifecycle evidence

- **WHEN** a managed delivery directly edits accepted `openspec/specs/*`
- **AND** there is no matching canonical change/archive evidence explaining those edits
- **THEN** publication fails closed as unexplained contract drift

#### Scenario: Matching change is archived and delivery remains

- **GIVEN** the managed change has matching provenance, completed tasks, semantic verification and archive evidence
- **WHEN** finish resumes after implementation completion
- **THEN** only remaining publication/reconciliation work proceeds
- **AND** no new OpenSpec materialization is required

### Requirement: Managed completeness uses existing OpenSpec evidence rather than fuzzy diff scoring

The platform SHALL use deterministic task checklist state, required semantic verification and archive/lifecycle evidence as the managed completion gate. It SHALL NOT use an LLM or fuzzy comparison between the original Issue body and code diff as the authoritative completeness boundary.

#### Scenario: Only part of the canonical task checklist is complete

- **WHEN** a managed task still has incomplete required OpenSpec tasks
- **THEN** terminal managed completion/publication SHALL NOT be reported solely because a PR exists or checks are green
