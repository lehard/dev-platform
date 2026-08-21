## ADDED Requirements

### Requirement: Project-harness rollout proves terminal reconciliation conformance

For a managed project-owned harness whose lifecycle requires terminal status
projection, rollout SHALL not treat platform version metadata advancement as
successful adoption unless the reviewed compatibility surface proves exact
merged-PR terminal reconciliation. Unknown or drifted project-owned harnesses
SHALL remain unchanged and block rollout.

#### Scenario: Recognized Planner-like harness receives terminal migration

- **GIVEN** the reviewed Planner-like publication and finish surfaces match the
  approved compatibility predicate
- **WHEN** rollout applies the terminal reconciliation release
- **THEN** exact merge proof, pending-reconciliation recovery and idempotent
  `Done` projection are installed without replacing standalone-clone behavior

#### Scenario: Planner-like harness cannot be proven safe

- **WHEN** either required compatibility surface has unknown or drifted bytes
- **THEN** rollout fails before advancing version metadata or modifying harness bytes
