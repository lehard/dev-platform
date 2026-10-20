## ADDED Requirements

### Requirement: OpenSpec authoring preserves Requirement binding levels

The platform's OpenSpec authoring guidance, in the central and generated repositories, SHALL direct the author to carry each material point of the source Business Requirement at the binding level the Requirement gave it. A fixed decision SHALL be written exactly. A point whose meaning is fixed and execution variable SHALL be written as the mandatory meaning or properties the user must be able to observe, with its presentation left open. A delegated detail SHALL NOT become a requirement. No requirement SHALL be bound more tightly than in the source Requirement, and an example, illustrative value or mockup SHALL NOT become an exact requirement unless the Requirement fixed it. Financial, technical, security and accessibility constraints and accepted scenarios SHALL keep their full force when presentation is delegated. The ADD pipeline SHALL keep these levels and SHALL NOT harden them in ADD elements, intents or handoff envelopes. The guidance SHALL include a worked example that separates a fixed meaning from its delegated presentation and SHALL apply to new authoring without requiring a rewrite of accepted specs.

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
