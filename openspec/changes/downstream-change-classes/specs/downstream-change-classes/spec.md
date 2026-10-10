## ADDED Requirements

### Requirement: Downstream contract distinguishes three change classes

The downstream platform contract SHALL distinguish ordinary project changes, temporary local hotfixes of platform-owned mechanisms that preserve every guarantee, and protected rules that no local change or recovery may bypass or alter. The contract SHALL NOT let an agent declare a safety, provenance or review gate safe to change on its own assumption.

#### Scenario: Agent classifies a needed change

- **GIVEN** a downstream agent needs to change a file
- **WHEN** it consults the shipped contract
- **THEN** the change is an ordinary project change, a hotfix-eligible platform change, or a protected change
- **AND** a protected change has no local path and is reported as requiring a platform release or the gate's own defined recovery.

### Requirement: Protected surface is shipped as versioned machine-readable data

The platform SHALL ship a machine-readable protected surface covering independent review, protected publication, isolation of other agents' worktrees, credential restrictions, routing, provenance and evidence authenticity, Git-history protection and immutable releases. The surface SHALL arrive only through a platform release and SHALL NOT be editable downstream.

#### Scenario: Every required category is covered

- **WHEN** the platform validates its template
- **THEN** each listed protected category maps to at least one existing protected path.

### Requirement: Every platform-owned file is classified without a default

Every plain-copied platform-owned file SHALL be classified protected or hotfixable. An unclassified file SHALL fail platform validation with a message naming the file; no default class applies.

#### Scenario: New unclassified script

- **GIVEN** a new platform-owned script is added to the template without a classification
- **WHEN** platform validation runs
- **THEN** it fails naming the script
- **AND** it does not treat the script as hotfixable or as protected.

### Requirement: The contract is delivered through the existing release and Copier mechanism

The change-class contract and protected surface SHALL be delivered to new and existing downstream projects through immutable releases and Copier rendering and update, without a new service or state registry.

#### Scenario: Existing project updates

- **WHEN** an existing project applies the release by Copier update
- **THEN** it receives the contract and protected surface
- **AND** project-owned files are unchanged.
