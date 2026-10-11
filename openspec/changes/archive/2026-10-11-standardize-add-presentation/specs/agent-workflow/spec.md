## ADDED Requirements

### Requirement: ADD preparation separates product contract from system delta

When preparing an Architecture Design Delta, the agent SHALL classify each candidate against the accepted Business Requirement, accepted OpenSpec and active deltas, project context, code/tests and bounded evidence, and SHALL place it in exactly one destination: an already accepted product contract, an existing authoritative technical contract, a real ADD delta, OpenSpec-level implementation detail, or an open product question. Only a new or changed material system-level contract, boundary, storage, data ownership, invariant, security concern or non-functional behavior relative to the current accepted state SHALL appear as a `new` or `changed` ADD delta. Product behaviour already defined by the Business Requirement SHALL be used as a constraint and SHALL NOT be re-presented as an architectural alternative requiring approval. An existing technical contract SHALL be referenced as preserved and SHALL NOT be re-offered as a choice. Naming of functions, handlers, files or code sequencing SHALL remain OpenSpec detail. A material missing product decision SHALL be marked as a clarification of the Business Requirement, not decided in the ADD. This classification SHALL be the agent's evidence-first judgement and SHALL NOT be a keyword or category gate or require an LLM judge. A bounded change without a useful design delta SHALL continue to skip ADD and intents.

#### Scenario: Detailed Business Requirement

- **WHEN** the Business Requirement already fixes several user-facing behaviours and rules
- **THEN** the ADD lists only the system-level changes they imply relative to the current system
- **AND** the fixed behaviours are not asked of the human again

#### Scenario: Real system delta

- **WHEN** an accepted behaviour requires a changed event contract, responsibility boundary, data ownership or invariant not set by the sources
- **THEN** the ADD states the difference from the current accepted state, the reason and the impact

#### Scenario: Decision already determined by evidence

- **WHEN** an authoritative existing contract determines the choice
- **THEN** the ADD references it as preserved and asks no human question

#### Scenario: Product uncertainty

- **WHEN** a material product decision is missing for correct development
- **THEN** it is shown as a clarification of the Business Requirement
- **AND** the agent neither decides it nor presents it among architectural alternatives

### Requirement: ADD is presented to the human through one standard read-only projection

Whenever the process shows an ADD to a human for a decision or approval, the presentation SHALL be the output of `add_intents.py render-add` for the current ADD document: a Russian Markdown message with the Business Requirement reference, target repository, ADD identity and content revision with a state derived from existing facts; a 2–4 sentence summary; a table of only the material `new`/`changed` deltas; what is preserved; questions that need the human with options, trade-offs and the recommendation where recorded, with product clarifications shown separately; and risks with one unambiguous next action. Sections without content SHALL be omitted. The state SHALL be «утверждён» only when the ADD is structurally valid, approved, its approval digest matches the current content and its freshness is proven; an approval that is stale or whose freshness cannot be proven SHALL render as «требует актуализации»; an ADD with an open choice or unresolved contradiction SHALL be «нужны решения»; an ADD without elements or choices SHALL be «предложение»; otherwise it SHALL be «готов к утверждению» only when its freshness is proven and «требует актуализации» when it is not. The projection SHALL be read-only, SHALL write no file or status, SHALL NOT approve, and SHALL fail explicitly on an ADD that is structurally invalid for any reason other than a stale approval digest. Its content SHALL NOT depend on the agent or project that invokes it. Presenting it SHALL add no mandatory human stop, no new approval mechanism and no project configuration.

#### Scenario: Open consequential alternative

- **WHEN** the ADD has an open architectural choice with options and a recommendation
- **THEN** the projection shows the options, trade-offs, recommendation and exact subject of decision in state «нужны решения»
- **AND** `approve-add` still refuses until it is resolved

#### Scenario: Product clarification

- **WHEN** the ADD records an open choice of kind product
- **THEN** the projection shows it under a separate heading as a clarification of the Business Requirement

#### Scenario: ADD edited after approval

- **WHEN** the material content of an approved ADD changes
- **THEN** the projection shows «требует актуализации» and the earlier approval is not presented as current
- **AND** after re-approval through the existing mechanism it shows «утверждён» for the new content

#### Scenario: Same ADD from different routes

- **WHEN** two agents or projects render the same ADD content
- **THEN** the output is identical in structure and wording of fixed labels

#### Scenario: No new process machinery

- **WHEN** the standard is delivered
- **THEN** no lifecycle stage, approval gate, semantic validator, decision registry, stored report, separate interface or per-project setting exists beyond the read-only command and the existing ADD fields
- **AND** no claim is made that structural checks prove the design is correct
