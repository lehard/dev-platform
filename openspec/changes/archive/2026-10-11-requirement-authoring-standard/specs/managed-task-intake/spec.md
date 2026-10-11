## ADDED Requirements

### Requirement: Business Requirement content is authored as a self-contained current contract

Before a Business Requirement body is written at fixation or materially changed at refinement, the authoring agent on every surface (repository agents and ChatGPT Project through connected GitHub) SHALL apply the single canonical Requirement authoring standard. The author SHALL use the whole relevant available context, SHALL separate accepted current requirements, explicitly accepted superseding refinements, examples and references, rejected or hypothetical material, and genuinely open material, and SHALL write only the current agreed result in affirmative form. A later explicitly accepted decision SHALL replace an earlier one; a last-mentioned option, an agent suggestion, a quotation or a hypothesis SHALL NOT be treated as accepted. Negotiation history SHALL NOT be copied; a still-active boundary SHALL be stated as the boundary and its material condition. The Requirement SHALL be understandable by an agent without the conversation, using only the Requirement and the materials it directly references.

Material, already-defined detail SHALL be carried over without loss: actors, rights and constraining contexts; scenarios, order, transitions, important exceptions and negative paths; agreed names, fields and input/answer rules; exact user-facing text and permitted wording; invariants for safety, truthfulness and compatibility; visual and interaction requirements; accepted delivery and acceptance conditions and explicit exclusions. Binding SHALL be evident at three levels: fixed (not changed without re-agreement), meaning fixed with variable execution, and delegated within the accepted corridor; delegation SHALL NOT permit changing product meaning, safety boundaries, data, rights or accepted scenarios, and SHALL NOT require agreement on immaterial choices. Acceptance evidence SHALL describe observable results and, where material, successful, failing and forbidden behavior. A narrow request SHALL NOT be widened into a global policy, a neighboring change or an unrequested feature. Length SHALL follow the content, not a template.

#### Scenario: Long discussion with several accepted details

- **GIVEN** a conversation that accepted exact texts, a scenario order and constraints
- **WHEN** the agent fixes the change
- **THEN** each material accepted detail appears in the Requirement
- **AND** a phrase such as "make it convenient" does not replace an agreed exact contract

#### Scenario: Earlier proposals were rejected

- **GIVEN** several options were discussed and one was explicitly accepted
- **WHEN** the Requirement is written
- **THEN** it states only the accepted result and any boundary that remains in force
- **AND** an unaccepted hypothesis is not presented as the user's choice

#### Scenario: A decision changes in an existing Requirement

- **WHEN** an accepted decision cancels an earlier one
- **THEN** Outcome, scenarios, Exclusions and Acceptance evidence are updated together as one current contract
- **AND** no obsolete mandatory criterion remains beside the new rule
- **AND** the children block, lifecycle-owned markers and BR revision binding are not edited by hand

#### Scenario: Fixed text versus example

- **WHEN** wording was agreed verbatim, agreed only in meaning, or offered as an optional example
- **THEN** the Requirement keeps the verbatim text verbatim, preserves every mandatory meaning of the permitted wording, and does not promote the optional example to a requirement

#### Scenario: Narrow request

- **WHEN** the accepted change is a specific prohibition or local behavior
- **THEN** the Requirement stays limited to it and creates no global policy or adjacent project

### Requirement: References are preserved reachable and unavailable material is declared

When the discussion supplied a screenshot, mockup, document, link or other reference, the Requirement SHALL preserve it through a permitted stable channel the executing agent can reach, SHALL name the properties of the reference that are mandatory, and SHALL declare any material the executor cannot access as unavailable. It SHALL NOT replace an unavailable attachment with a link to a changing site root, and SHALL NOT copy private conversations, secrets, unreachable personal files or whole external documents into a public repository.

#### Scenario: Reference available to the executor

- **WHEN** a mockup or link is accessible to the executing agent
- **THEN** the Requirement references it durably and states the visual or semantic properties that must hold

#### Scenario: Attachment not accessible

- **WHEN** an attachment cannot be reached by the executing agent
- **THEN** the Requirement states that it is unavailable and what is known from it
- **AND** does not point to a mutable homepage as a substitute

### Requirement: Authoring questions are limited to unresolved material product choices

Before writing, the author SHALL reconcile the conversation, supplied materials and available authoritative product context and SHALL ask the human only when proceeding would require choosing something that materially changes the product result, rights, money or data invariants, essential scope or the meaning of an earlier decision. Questions SHALL be brief, grouped (normally one to three per pass), explain the choice and consequence where useful, and SHALL NOT repeat an answered question, ask a technical ADD/OpenSpec question, demand empty sections or run a mandatory interview. Minor missing detail SHALL be delegated to the executor and the Requirement fixed without delay. A critical unresolved choice SHALL NOT be written as agreed; the author asks before fixation or keeps the idea as an incubated, unaccepted item under the existing Incubator contract. This pre-fixation check SHALL NOT replace later evidence-first ADD/OpenSpec resolution.

#### Scenario: Material product fork unresolved

- **WHEN** two incompatible outcomes remain and no accepted choice can be determined
- **THEN** the author asks a brief question with the consequence of each option rather than guessing

#### Scenario: Question already answered or immaterial

- **WHEN** the answer is already in the conversation or the gap is cosmetic or technical
- **THEN** the author does not interrupt fixation and delegates or uses the stated answer

#### Scenario: Compact obvious request

- **WHEN** the request is short and unambiguous
- **THEN** the Requirement is compact, without a questionnaire or empty subsections

### Requirement: The authoring standard is a working discipline, not a lifecycle element

Before writing and after any material edit the author SHALL check coverage, consistency, scope, autonomy, portability and truthfulness of the Requirement as a lightweight internal practice. This SHALL NOT introduce a blocking or LLM semantic validator, scorecard, approval stage, lifecycle status, separate backlog, list of unresolved questions, per-project configuration or new storage, and SHALL NOT change the Requirement format, routing, labels, children markers, BR revision binding, pre-authoring or quick-task behavior. Transport and confirmation of fixation SHALL remain as specified, and creating the Requirement SHALL NOT start implementation.

#### Scenario: Standard applied on a surface without checkout

- **WHEN** a ChatGPT Project fixes a Requirement through connected GitHub
- **THEN** it follows the same standard and the same Issue representation as a repository agent
- **AND** no extra stage, gate or user action is added

#### Scenario: Existing process is unchanged

- **WHEN** a Requirement authored under the standard is created, read back, started and executed
- **THEN** routing, labels, Project membership, children block, revision binding and ADD/OpenSpec behave as before
