# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Shared Requirement publication recovers after main advances

The shared Requirement publisher SHALL preserve exact verified child provenance and produce a new base-bound candidate generation when authoritative main advances before publication. It SHALL NOT rewrite child branches, take over an earlier candidate, or bypass full checks and protected PR authority.

#### Scenario: Unrelated main change is replayed safely

- **GIVEN** a clean prior candidate and exact child receipts based on an older main
- **WHEN** an unrelated protected change advances main before the candidate's first PR
- **THEN** a distinct candidate generation applies the same exact child deltas to current main
- **AND** the prior candidate remains untouched
- **AND** the new candidate must pass full validation and protected publication before terminal status

#### Scenario: Recovery fails closed

- **GIVEN** a changed child head, conflicting patch, occupied generation or mismatched local source contract
- **WHEN** the candidate is resumed or composed
- **THEN** no unrelated worktree is reset, overwritten, force-pushed or published
- **AND** the blocker identifies the exact failed boundary

#### Scenario: Candidate receives its local validation contract

- **GIVEN** the integration checkout uses an ignored `.dev-platform.toml` for source validation
- **WHEN** a candidate worktree is created or resumed
- **THEN** it receives the same-content local contract without changing tracked candidate files
- **AND** validation does not silently fall back to a different operator profile
