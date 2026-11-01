## ADDED Requirements

### Requirement: Gate evidence survives a main-only integration

After an integration repair or derived merge, the developer receipt and its gates SHALL stay valid when the new head's tree equals, byte for byte, the merge of the old head with the new base, conflicting only in generated files declared on the default branch. The old head SHALL come only from a trusted queue record of the transition where the gates passed; a missing or malformed record SHALL reset the receipt with a reason.

#### Scenario: Main touched a task path

- **GIVEN** a candidate whose gates passed at a trusted head
- **WHEN** the coordinator merges main that also changed a task path and the new head equals that merge
- **THEN** the receipt and the gates bound to it are reused for the new head

#### Scenario: Integration changed own content

- **WHEN** the new head differs from the merge of the old head with the new base
- **THEN** fresh developer semantic verification is required through handoff

#### Scenario: No trusted record

- **WHEN** no trusted queue record names the head on which the gates passed
- **THEN** the receipt is reset with a reason and nothing is reused
