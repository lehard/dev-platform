# platform-lifecycle Specification Delta

## ADDED Requirements

### Requirement: Shared integration publication preserves exact provenance and protected checks

A requirement-level integration candidate SHALL bind its main base and ordered exact child heads, fail closed on stale or ambiguous inputs, and use the existing protected full-check and PR authority for final publication.

#### Scenario: A child or base changes before publication

- **WHEN** a bound child head or the authoritative main base changes before final validation
- **THEN** integration stops or explicitly reconciles and revalidates the new candidate
- **AND** it never publishes an unvalidated head or silently rewrites another worktree

#### Scenario: Candidate child edits overlap

- **WHEN** two independently handed-off child heads claim the same changed path relative to the bound base
- **THEN** candidate assembly fails before creating a publication object
- **AND** the failure identifies the conflicting children and paths

#### Scenario: The combined candidate fails verification

- **WHEN** interaction or required full checks fail
- **THEN** no child or parent is projected as terminal

#### Scenario: An interrupted publication resumes

- **GIVEN** an exact integration PR or merge is already present
- **WHEN** the operation is retried
- **THEN** it reuses and reconciles that exact publication object without duplicate PRs or false child completion
