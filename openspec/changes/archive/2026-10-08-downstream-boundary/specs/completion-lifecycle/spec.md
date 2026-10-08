## ADDED Requirements

### Requirement: Lifecycle behavior is selected from the committed contract before source-only logic

Archive, publication and Requirement lifecycle entrypoints SHALL select portable or coordinator behavior from the committed `.dev-platform.toml` contract through one repository-owned selector before importing or evaluating any source-only coordinator logic. A downstream contract (`platform_version` other than `source`) SHALL select portable behavior. The source contract SHALL select coordinator behavior only for `harness_mode=platform`, `publish_mode=pr` and `scm_provider=github`; any other source combination, or a missing `platform_version`, SHALL fail with a named error and SHALL NOT switch to another path.

#### Scenario: Downstream archive stays portable
- **WHEN** a downstream-contract checkout runs `openspec_lifecycle.py archive` for a completed verified change and the coordinator modules are unavailable
- **THEN** archive completes through the portable review and checks path without importing `pr_review_gate`, `publication_queue` or `lifecycle_workers`

#### Scenario: Downstream ignores coordinator candidacy
- **WHEN** a downstream-contract checkout has ambiguous or malformed managed provenance and the candidate question is asked
- **THEN** it answers not-a-coordinator-candidate without resolving provenance and without raising

#### Scenario: Unsupported source combination fails explicitly
- **WHEN** the source contract declares `scm_provider=gitlab`, `publish_mode=direct` or `harness_mode=project`
- **THEN** Requirement lifecycle selection raises an error naming the key and value and does not fall back to the legacy or portable path

#### Scenario: Supported source contract keeps coordinator behavior
- **WHEN** the source contract declares the supported combination
- **THEN** coordinator candidacy and publication support are evaluated exactly as before, and provenance errors still propagate
