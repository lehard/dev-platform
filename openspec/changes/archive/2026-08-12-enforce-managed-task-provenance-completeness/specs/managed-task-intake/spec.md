## ADDED Requirements

### Requirement: Managed-task provenance remains resolvable after materialization

After a managed package is materialized, the repository SHALL retain deterministic provenance sufficient to resolve the source Development Backlog Issue and canonical repository-local OpenSpec change during later resume and delivery. The original package content SHALL NOT become a second canonical implementation plan.

#### Scenario: Managed task resumes with an active canonical change

- **GIVEN** a managed task was materialized from source Issue A
- **AND** the repository-local active change records matching provenance to Issue A
- **WHEN** execution resumes from the existing branch/worktree
- **THEN** the lifecycle reuses that canonical change
- **AND** does not re-import or overwrite it from the original backlog package

#### Scenario: Managed task resumes after canonical change was archived

- **GIVEN** the matching repository-local change was semantically verified and archived
- **WHEN** only publication/reconciliation work remains
- **THEN** provenance to Issue A remains resolvable from the archived lifecycle evidence
- **AND** resume does not create a second active change

#### Scenario: Canonical change is missing or belongs to another source

- **WHEN** a managed branch/worktree/PR claims source Issue A but no matching active/archived canonical change exists, or the same-name change records different provenance
- **THEN** managed resume fails closed with an actionable recovery state
- **AND** does not continue implementation/publication based only on branch, PR title or change name

### Requirement: Canonical OpenSpec may evolve without losing source provenance

The platform SHALL distinguish legitimate repository-local OpenSpec evolution from provenance loss. A canonical managed change MAY diverge from the original transport package under the existing no-silent-divergence rules, while retaining its source Issue identity.

#### Scenario: Implementation updates design or tasks after materialization

- **GIVEN** the repository-local change still identifies the same source managed Issue
- **WHEN** implementation validly updates proposal/design/spec/tasks according to the repository lifecycle
- **THEN** later provenance validation accepts the evolved canonical change
- **AND** does not require byte equality with the original managed package
