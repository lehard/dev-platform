## ADDED Requirements

### Requirement: Archive-derived spec conflicts are re-derived deterministically

When preparing a candidate on current main, conflicts confined to archive-derived current-spec paths SHALL be resolved by re-applying the candidate's archived delta specs on the actual base. A failed re-application SHALL become integration repair. A successful re-application SHALL be bookkeeping only: it SHALL NOT replace required checks on the actual candidate and SHALL NOT mask a semantic or contract conflict.

#### Scenario: Two candidates extend one capability
- **GIVEN** candidate A merged a change to a capability spec
- **WHEN** candidate B, archived earlier against older main, is prepared
- **THEN** B's deltas are re-applied on the new spec and checks run on the result
