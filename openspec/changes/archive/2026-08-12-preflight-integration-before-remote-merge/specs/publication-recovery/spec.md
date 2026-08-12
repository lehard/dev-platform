## ADDED Requirements

### Requirement: Confirmed remote merge remains authoritative across dirty local reconciliation

Once GitHub confirms the exact task PR as `MERGED`, the platform SHALL preserve that remote fact even if local integration reconciliation is blocked by uncommitted state. Recovery SHALL distinguish content that can be proven equivalent to the authoritative remote target from divergent local content and SHALL only normalize/reconcile the equivalent case without data loss.

#### Scenario: Remote merge is confirmed and local content is equivalent

- **GIVEN** GitHub reports the exact task PR as `MERGED`
- **AND** local integration contains working-tree/index state whose relevant content can be proven equivalent to the authoritative current remote target
- **WHEN** finish recovery runs under integration serialization
- **THEN** it MAY perform the bounded reconciliation needed to converge local integration to the remote target
- **AND** does not discard distinct user content

#### Scenario: Remote merge is confirmed and local content diverges

- **GIVEN** GitHub reports the exact task PR as `MERGED`
- **AND** local integration contains content not proven equivalent to the authoritative remote target
- **WHEN** recovery runs
- **THEN** it reports remote delivery as merged but local reconciliation blocked
- **AND** names the conflicting local paths
- **AND** leaves that content untouched

#### Scenario: Recovery is retried after local blocker is resolved

- **WHEN** the local integration blocker is safely resolved outside destructive platform cleanup
- **THEN** a later finish invocation reuses the same exact merged PR evidence
- **AND** completes only the remaining local reconciliation/cleanup without creating a second PR
