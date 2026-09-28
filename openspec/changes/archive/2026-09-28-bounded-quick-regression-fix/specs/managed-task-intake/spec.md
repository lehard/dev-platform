## MODIFIED Requirements

### Requirement: Quick work escalates to managed intake before becoming a material OpenSpec change

Quick execution SHALL remain available for small bounded work, including a repair that restores unambiguously accepted behavior when the user requests execution now. The repair SHALL identify the accepted contract and retain proportionate regression evidence. When a reasonable test seam exists, its regression check SHALL fail before the repair and pass after it, and the original failure path SHALL be rerun. When no reasonable seam exists, the limitation and the actual alternative check SHALL be recorded without fabricated evidence. Applicable safety, check, verification, and publication gates SHALL still apply. If quick work changes behavior, architecture, compatibility, a data contract, or material scope, or needs a full active OpenSpec change, the platform SHALL stop further quick implementation and enter requirement-first intake, except when the user explicitly requests the direct technical managed path. This SHALL use the existing quick and managed lifecycles and SHALL NOT change release-bundling policy.

#### Scenario: Directly requested bounded regression repair

- **GIVEN** an accepted spec or durable contract unambiguously establishes the expected behavior
- **AND** a small defect violates that behavior
- **WHEN** the user requests the repair now
- **THEN** the repair may use the existing quick lifecycle without a new Requirement or OpenSpec delta
- **AND** it records proportionate regression evidence and passes applicable safety and publication gates

#### Scenario: Representative quick fix stays bounded

- **GIVEN** a small clear change needs no full OpenSpec contract
- **WHEN** the user requests immediate execution
- **THEN** the quick lifecycle may execute without a Backlog Issue or ceremonial OpenSpec

#### Scenario: Reasonable regression seam exists

- **GIVEN** a bounded quick regression repair has a reasonable test seam
- **WHEN** the repair is completed
- **THEN** a check demonstrated the defect before the repair and passes after it
- **AND** the original failure path is rerun

#### Scenario: No reasonable regression seam exists

- **GIVEN** no reasonable automated test seam exists for a bounded repair
- **WHEN** the repair is completed
- **THEN** the limitation and the actual alternative check are recorded truthfully

#### Scenario: Quick repair reveals a contract change

- **GIVEN** a repair began through quick execution
- **WHEN** investigation reveals new behavior, architecture, compatibility, data-contract, or material scope work
- **THEN** further quick implementation stops
- **AND** work continues only through requirement-first intake and its linked managed child, unless direct technical managed intent was explicit

#### Scenario: Quick task grows into a material change

- **GIVEN** work began as quick execution
- **WHEN** inspection reveals material scope or need for a full active OpenSpec contract
- **THEN** further implementation stops and the accepted scope is recorded or reused as a Business Requirement
- **AND** work continues only after pre-authoring and a linked managed technical child establish canonical OpenSpec provenance

#### Scenario: Genuine quick work has no OpenSpec change

- **GIVEN** a bounded quick task never created an active OpenSpec change
- **WHEN** it uses the supported quick lifecycle
- **THEN** absence of managed provenance alone does not force backlog creation
