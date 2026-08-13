## ADDED Requirements

### Requirement: Codex execution provenance is verified against a real live run

The "Routed Codex executor actually runs" scenario for truthful bounded execution provenance SHALL be verified at least once against a real, live `codex` CLI invocation through the platform-owned `dispatch_codex()`/`run_codex()` path, not solely through simulated stdout event lines in unit tests.

#### Scenario: Live Codex delegation confirms real provenance capture

- **GIVEN** a real authenticated `codex` CLI is available and a routine/standard Codex route is prepared for a real managed task
- **WHEN** `run_codex()` launches that route through the real CLI
- **THEN** the resulting `execution.participant` carries a real bounded execution identifier captured from the live `--json` event stream
- **AND** model/reasoning-effort source/status reflect only what the live run actually confirmed, with no field upgraded to `runtime-confirmed` without live evidence
