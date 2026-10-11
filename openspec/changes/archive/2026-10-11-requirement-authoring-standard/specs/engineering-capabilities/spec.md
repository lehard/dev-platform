## ADDED Requirements

### Requirement: The requirement-authoring capability is the single canonical authoring standard

Dev Platform SHALL provide an instruction-only capability `requirement-authoring` whose Markdown is the one canonical source of the Business Requirement authoring standard and its small representative examples, with a descriptor and deterministic eval fixture following the capability lifecycle. Task intake, the ChatGPT Project protocol, agent instructions and the repository map SHALL reference that source rather than restate or fork its rules, so that repository agents, ChatGPT Project and managed downstream projects apply the same standard. The standard SHALL be reachable through the delivered files without enabling the capability or editing any project file; enabling the capability SHALL additionally materialize the same content as the native provider skill. The capability SHALL NOT create storage, gates, status, approvals, tool runtime or application dependencies.

#### Scenario: Project has not enabled the capability

- **WHEN** a managed project renders or updates without enabling `requirement-authoring`
- **THEN** the canonical standard file and the pointers to it are present
- **AND** no provider skill, runtime or project configuration is added solely because of it

#### Scenario: Project enables the capability

- **WHEN** the capability is enabled
- **THEN** Claude and Codex skills contain the same standard content as the canonical file
- **AND** no surface carries a divergent copy of the rules

#### Scenario: Cross-provider verification is not available live

- **WHEN** a live multi-provider behavioral run cannot be performed
- **THEN** the deterministic fixture and rendered-surface identity checks are recorded as the evidence
- **AND** no cross-provider behavior is claimed as verified
