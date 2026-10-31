## ADDED Requirements

### Requirement: A developer does not archive a coordinator candidate

Under the coordinator lifecycle a developer archive of a coordinator-managed candidate SHALL be refused before any review, check or OpenSpec change, naming the handoff command, because the candidate is handed off with its change still active and the coordinator's finalize archives it. The finalize archive SHALL be unchanged.

#### Scenario: Developer archives a coordinator candidate

- **GIVEN** the coordinator lifecycle with the publication queue enabled and an active coordinator-managed candidate
- **WHEN** the developer runs `openspec_lifecycle.py archive <change>` without `--finalize`
- **THEN** it fails before any work, naming the handoff command
- **AND** the change stays active

#### Scenario: Coordinator finalize archives

- **WHEN** finalize runs `openspec_lifecycle.py archive <change> --finalize` for a reviewed candidate
- **THEN** the archive proceeds as before
