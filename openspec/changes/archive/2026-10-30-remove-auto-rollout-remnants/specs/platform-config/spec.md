## MODIFIED Requirements

### Requirement: Operator handoff is explicit before fleet rollout

The public source SHALL document the external fields required for the current operator to resume managed fleet rollout after private compatibility data has been removed from source. Documentation SHALL name configuration keys and validation commands, but SHALL NOT commit the operator's real repository inventory, tokens, or credentials.

#### Scenario: Operator prepares for next real rollout
- **WHEN** public cutover preparation is complete
- **THEN** the handoff checklist identifies at least the external Development Backlog configuration, `rollout.registry_path` and rollout bot identity as applicable
- **AND** it identifies a validation/doctor command to prove the external configuration before fleet mutation
- **AND** absence of required real configuration causes rollout to fail closed rather than fall back to hidden public defaults.
