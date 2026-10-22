## ADDED Requirements

### Requirement: The hosted pilot ends in a recorded placement decision

A bounded pilot on real pull requests of the platform repository SHALL end in a durable record of, for each hosted lifecycle job kind, whether it runs hosted or remains on the local fallback, with the verified constraints behind the decision: provider runtime and credential availability, credential-boundary proof, token scope, observed duration, cost and limits, and failure behavior. A value that cannot be observed SHALL be recorded as unobserved with the reason and SHALL NOT be estimated as measured. A kind whose prerequisites cannot be proven SHALL stay off the hosted path and the record SHALL name the basis for the local operator node. The pilot SHALL introduce no second orchestrator, queue or state store and SHALL give no local worker merge authority.

#### Scenario: Prerequisite proven

- **WHEN** a kind's preflight and a real-PR run succeed
- **THEN** the record states it as hosted with the observed constraints

#### Scenario: Prerequisite unprovable

- **WHEN** a runtime, credential, containment or access prerequisite cannot be proven
- **THEN** the record keeps the kind off the hosted path and names the basis for the local operator node
- **AND** no kind is moved to CI by default

#### Scenario: Value not observable

- **WHEN** a constraint such as per-job provider cost cannot be observed
- **THEN** the record marks it unobserved with the reason instead of an estimate

#### Scenario: Local fallback is not widened

- **WHEN** the record recommends the local fallback for a kind
- **THEN** it grants that worker no merge or `main` authority beyond the existing CI-only protocol
