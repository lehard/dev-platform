## ADDED Requirements

### Requirement: Requirement advance resolves handoff, bundle and child by one key

`execute_requirement.py advance` SHALL resolve a handoff's authored bundle by the handoff id: the bundle directory named after it, or the single bundle whose manifest declares that handoff. The bundle's `change` SHALL name the managed change. A handoff whose bundle is ambiguous or malformed SHALL stop naming the bundles involved. When a linked child that is not terminal maps to no current handoff, advance SHALL fail naming that child, its change and the handoffs left unmapped, with the bundle naming rule as the next action.

#### Scenario: Intent and change named differently

- **GIVEN** handoff `I1` whose child was materialized as change `object-client-contract` from bundle `bundles/object-client-contract` declaring `"handoff": "I1"`
- **AND** the handoff was refreshed after materialization
- **WHEN** advance runs
- **THEN** handoff `I1` maps to that child and advance continues without a historical-child error

#### Scenario: Mismatched names

- **GIVEN** the same refreshed handoff and a bundle `bundles/object-client-contract` without a handoff declaration
- **WHEN** advance runs
- **THEN** it fails naming handoff `I1`, the linked child and change `object-client-contract`, and the bundle naming rule

#### Scenario: Two bundles claim one handoff

- **WHEN** two bundle manifests declare the same handoff
- **THEN** advance stops naming both bundles
