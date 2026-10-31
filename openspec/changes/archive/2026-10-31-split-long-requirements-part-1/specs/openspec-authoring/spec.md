## MODIFIED Requirements

### Requirement: OpenSpec stable-version upgrades preserve lifecycle correctness

Dev Platform SHALL update its supported OpenSpec compatibility baseline only after the selected stable release passes representative managed lifecycle checks and focused regressions for correctness-sensitive upstream changes.

#### Scenario: Stable OpenSpec upgrade passes compatibility checks
- **WHEN** a newer stable OpenSpec release is selected for adoption
- **AND** representative materialize, validate, semantic verify and archive checks pass
- **AND** focused regressions for the motivating upstream correctness changes pass
- **THEN** the platform MAY update its minimum/tested OpenSpec version contract and matching fixtures/docs consistently
- **AND** SHALL retain platform semantic verification and lifecycle evidence unless a separate reviewed change proves a guard redundant

#### Scenario: Compatibility check finds a material regression
- **WHEN** the selected stable OpenSpec release violates a Dev Platform lifecycle invariant or fails a representative regression
- **THEN** the platform SHALL keep the existing supported contract
- **AND** SHALL record the incompatibility instead of weakening verification, archive, or source-of-truth guarantees merely to complete the dependency bump

#### Scenario: Adopted release fixes are pinned by behavior
- **GIVEN** a stable OpenSpec release is adopted because it fixes archive, validation, task-progress or verification correctness
- **WHEN** platform CI runs the exact-CLI regression suite against the pinned version
- **THEN** each motivating fix is exercised by a fixture that would fail against the previously tested version
- **AND** no recorded copy of the previous tested version remains in the platform or rendered template

### Requirement: OpenSpec authoring preserves Requirement binding levels

The platform's OpenSpec authoring guidance, in the central and generated repositories, SHALL direct the author to carry each material point of the source Business Requirement at the binding level the Requirement gave it.

#### Scenario: Meaning fixed, presentation delegated

- **GIVEN** a Requirement states that a warning must be visible next to the balances with its meaning fixed and its presentation left to the executor
- **WHEN** the author writes the OpenSpec requirement
- **THEN** the requirement states the meaning the user must observe and where it must be observable
- **AND** it does not prescribe the widget, icon, exact wording beyond agreed text or placement inside the area

#### Scenario: Fixed decision stays exact

- **GIVEN** the same Requirement fixes the order of a switch and the absence of horizontal scrolling at 375 px
- **WHEN** the author writes the OpenSpec requirements
- **THEN** both are written exactly and checked by scenarios

#### Scenario: Example is not a requirement

- **GIVEN** a Requirement shows a mockup with illustrative amounts
- **WHEN** the author writes the OpenSpec requirements
- **THEN** the amounts and pixel layout do not appear as required values unless the Requirement fixed them

## ADDED Requirements

### Requirement: Every recorded copy of the tested OpenSpec version moves together

Every recorded copy of the tested OpenSpec version -- the rendered `[tools.openspec]` configuration, every platform or rendered workflow that installs or invokes the OpenSpec CLI, and the tested-version documentation -- SHALL move together.

#### Scenario: Tested OpenSpec version changes

- **WHEN** the tested OpenSpec version changes
- **THEN** the rendered `[tools.openspec]` configuration, every platform or rendered workflow that installs or invokes the OpenSpec CLI, and the tested-version documentation move together

### Requirement: Adopted OpenSpec release fixes stay in the exact-CLI regression suite

The focused regressions for an adopted release's correctness fixes SHALL remain in the exact-CLI regression suite that platform CI runs against the pinned version.

#### Scenario: Adopted release has correctness fixes

- **GIVEN** an adopted OpenSpec release with correctness fixes
- **WHEN** platform CI runs the exact-CLI regression suite against the pinned version
- **THEN** the focused regressions for those fixes remain in that suite

### Requirement: A fixed Requirement decision is written exactly

A fixed decision SHALL be written exactly.

#### Scenario: Fixed decision is authored

- **GIVEN** a source Business Requirement fixes a decision
- **WHEN** the author writes the OpenSpec requirement
- **THEN** the decision is written exactly

### Requirement: A meaning-fixed point is written as observable meaning

A point whose meaning is fixed and execution variable SHALL be written as the mandatory meaning or properties the user must be able to observe, with its presentation left open.

#### Scenario: Meaning fixed, execution variable

- **GIVEN** a source Business Requirement point whose meaning is fixed and execution variable
- **WHEN** the author writes the OpenSpec requirement
- **THEN** it is written as the mandatory meaning or properties the user must be able to observe
- **AND** its presentation is left open

### Requirement: A delegated Requirement detail does not become a requirement

A delegated detail SHALL NOT become a requirement.

#### Scenario: Delegated detail

- **GIVEN** a source Business Requirement delegates a detail
- **WHEN** the author writes the OpenSpec requirements
- **THEN** the delegated detail does not become a requirement

### Requirement: No requirement is bound more tightly than its source Requirement

No requirement SHALL be bound more tightly than in the source Requirement.

#### Scenario: Binding level is compared

- **WHEN** the author writes an OpenSpec requirement from a source Requirement
- **THEN** it is not bound more tightly than in the source Requirement

### Requirement: An example in a Requirement does not become an exact requirement

An example, illustrative value or mockup SHALL NOT become an exact requirement unless the Requirement fixed it.

#### Scenario: Example, illustrative value or mockup

- **GIVEN** a source Requirement contains an example, illustrative value or mockup it did not fix
- **WHEN** the author writes the OpenSpec requirements
- **THEN** it does not become an exact requirement

### Requirement: Constraints and accepted scenarios keep full force when presentation is delegated

Financial, technical, security and accessibility constraints and accepted scenarios SHALL keep their full force when presentation is delegated.

#### Scenario: Presentation is delegated

- **GIVEN** a source Requirement with financial, technical, security or accessibility constraints and accepted scenarios
- **WHEN** presentation is delegated
- **THEN** those constraints and accepted scenarios keep their full force

### Requirement: The ADD pipeline keeps Requirement binding levels

The ADD pipeline SHALL keep these Requirement binding levels and SHALL NOT harden them in ADD elements, intents or handoff envelopes.

#### Scenario: Binding levels pass through the ADD pipeline

- **WHEN** the ADD pipeline processes a Requirement
- **THEN** it keeps the Requirement binding levels
- **AND** it does not harden them in ADD elements, intents or handoff envelopes

### Requirement: OpenSpec authoring guidance includes a worked binding-level example

The platform's OpenSpec authoring guidance SHALL include a worked example that separates a fixed meaning from its delegated presentation.

#### Scenario: Guidance is read

- **WHEN** an author reads the platform's OpenSpec authoring guidance
- **THEN** it includes a worked example that separates a fixed meaning from its delegated presentation

### Requirement: Binding-level authoring guidance applies to new authoring only

The platform's OpenSpec authoring guidance SHALL apply to new authoring without requiring a rewrite of accepted specs.

#### Scenario: Accepted specs exist

- **GIVEN** accepted specs written before the binding-level guidance
- **WHEN** the guidance applies
- **THEN** it applies to new authoring
- **AND** no rewrite of accepted specs is required
