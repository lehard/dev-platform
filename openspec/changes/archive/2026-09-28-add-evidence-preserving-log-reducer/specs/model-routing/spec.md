## ADDED Requirements

### Requirement: Execution logs may be reduced only while exact source evidence remains authoritative

After the large-observation lifecycle preserves an eligible execution log, Dev Platform MAY derive a compact structured receipt for active-context use. The original log and canonical command/result evidence SHALL remain authoritative, and a reducer receipt SHALL NOT replace test, CI or completion pass/fail semantics.

Known deterministic fields SHOULD be parsed directly when practical before model-based semantic reduction is used.

#### Scenario: Noisy failing log is reduced

- **GIVEN** an eligible execution log is preserved as an exact cold observation
- **WHEN** a supported reducer creates a compact receipt
- **THEN** the receipt references the preserved source identity
- **AND** retains the bounded failure facts/evidence needed for navigation
- **AND** the original remains exactly recallable
- **AND** canonical command/check outcome remains owned by the source execution

#### Scenario: Deterministic log structure already exposes the fact

- **GIVEN** a supported log format exposes exit status or another required field deterministically
- **WHEN** the receipt is built
- **THEN** the platform uses the deterministic field as its source
- **AND** does not require a model to reinterpret that field merely for consistency
- **AND** an exact bounded log line MAY form a receipt without model output when its receipt is smaller than the existing hot representation

### Requirement: Reducer receipts require deterministic evidence binding

A semantic reducer receipt SHALL be trusted only to the extent that its evidence-bearing claims can be bound back to the preserved source. Source handle/digest, exact quoted/ranged evidence and structured command/result fields SHALL be validated where applicable. Failure, low confidence or validation mismatch SHALL fall back to exact source evidence rather than produce a verified receipt.
The archive-time digest SHALL also match the stored source at reduction time. A receipt SHALL be used as the hot representation only when it is smaller than the source and the existing hot reference.
If the preserved source cannot be read or fails integrity verification, reduction SHALL report source unavailability rather than claim that fallback evidence is recallable.

#### Scenario: Reducer invents an error quote

- **GIVEN** a receipt contains a quote or range not present at the claimed source location
- **WHEN** receipt verification runs
- **THEN** the receipt is rejected as unverified
- **AND** the caller can use the preserved exact source
- **AND** no verification success is derived from the fabricated receipt

#### Scenario: Reducer reports a result inconsistent with canonical exit evidence

- **GIVEN** canonical command evidence records a failing exit status
- **BUT** the receipt claims the command passed
- **WHEN** receipt verification runs
- **THEN** the receipt is rejected
- **AND** canonical execution evidence remains authoritative

### Requirement: Reducer-efficiency evidence reuses execution provenance

Reducer execution SHALL reuse bounded routing/execution provenance where practical. The platform MAY record reducer profile/participant, source and receipt volume, reducer verification outcome, fallback/recall volume and exact supported runtime usage. It SHALL NOT create a transcript warehouse or infer canonical token savings from byte/line reduction.

#### Scenario: Routine reducer is unavailable

- **WHEN** the configured reducer cannot run safely in the current runtime
- **THEN** the exact source path remains available
- **AND** provenance records the actual fallback rather than a successful reducer execution
