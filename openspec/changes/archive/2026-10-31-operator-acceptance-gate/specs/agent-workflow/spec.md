## ADDED Requirements

### Requirement: Operator acceptance items keep a Requirement open

A Requirement MAY declare operator acceptance items in a `## Operator acceptance` section, each with an id, the owner's action and a check command. While any item has no owner decision, terminal reconciliation SHALL refuse to close the Requirement, naming the items, and the lifecycle overview SHALL list it as waiting for the owner with the check and the accept command.

#### Scenario: Open item after the last merge
- **WHEN** every child merged and an item has no decision
- **THEN** the post-merge terminal job records `requirement-awaits-owner-acceptance` naming it, spends no attempt and leaves the Requirement open

#### Scenario: Malformed section
- **WHEN** an item line has no check command or repeats an id
- **THEN** reading the Requirement fails naming the line

### Requirement: The owner's acceptance decision closes through the single closer

`requirement_terminal.py accept` SHALL record a confirmed or waived decision for one declared item with actor, reason and via on the Requirement Issue, and SHALL close the Requirement through the same terminal reconciliation once no item is open. It SHALL refuse an unknown item or a closed Requirement without writing.

#### Scenario: Last item confirmed
- **WHEN** the owner confirms the last open item and every child is delivered
- **THEN** the decision is recorded and the Requirement is closed

#### Scenario: Other items still open
- **WHEN** an item is confirmed but another has no decision
- **THEN** the decision is recorded and the command reports the remaining items without closing
