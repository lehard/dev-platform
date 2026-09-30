## ADDED Requirements

### Requirement: Independent review reports retain runtime-returned usage

When a reviewer runtime returns structured usage for a review launch, the platform SHALL retain it in that perspective's report as a bounded, runtime-local usage block with a value, source and status per field. It SHALL NOT retain prompts, responses or monetary cost. Unsupported, malformed or ambiguous fields SHALL be unknown, never zero. The block SHALL NOT affect review acceptance, freshness or disposition binding, and reports without it SHALL remain valid.

#### Scenario: Claude Code reviewer returns usage
- **GIVEN** a Claude Code reviewer launch returns a structured result with usage and duration fields
- **WHEN** the report is written
- **THEN** those fields are recorded as runtime-confirmed measurements under the Claude runtime

#### Scenario: Codex reviewer emits more than one completion
- **GIVEN** a Codex reviewer launch emits more than one completion usage event
- **WHEN** the report is written
- **THEN** its token fields are unknown rather than summed

#### Scenario: Historical report without usage
- **WHEN** a report written before this change is validated
- **THEN** it remains valid and its usage reads as unknown
