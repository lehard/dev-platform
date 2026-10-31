## ADDED Requirements

### Requirement: Source route commands take a routing tier

`dogfood_task.py route-claude` and `route-codex` SHALL take `--tier R1|R2|R3` and route as the profile it maps to (R1 routine, R2 standard, R3 complex); omitting it SHALL confirm the authored tier. `--profile` SHALL be refused with an error naming `--tier`. Source docs and hints SHALL name only R1/R2/R3 for these commands.

#### Scenario: Explicit tier
- **WHEN** `route-claude --tier R2` runs
- **THEN** it records the same route as the former `--profile standard`

#### Scenario: Old flag
- **WHEN** `route-codex --profile standard` runs
- **THEN** it fails naming `--tier` and records nothing
