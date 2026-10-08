## ADDED Requirements

### Requirement: Shipped capability eval fixtures are consistent and continuously evaluated

Every eval fixture shipped in `dev-platform/evals/` and `template/dev-platform/evals/` SHALL bind by `content_sha256` to the current canonical descriptor of its capability and SHALL evaluate successfully against it. The source and template fixture sets SHALL be identical. A repository-owned regression check SHALL evaluate every shipped fixture against its descriptor so that a stale binding or a source/template divergence fails platform validation with an explicit error naming the fixture.

#### Scenario: Fixture binds to a changed descriptor
- **WHEN** a capability's instructions or descriptor hash changes and its shipped fixture still carries the previous `content_sha256`
- **THEN** the regression check fails and names the fixture and the hash mismatch
- **AND** the direct `capability_manager.py evaluate` path reports the same mismatch instead of running the fixture

#### Scenario: Shipped fixtures are current
- **WHEN** the regression check runs on a consistent source tree
- **THEN** every fixture in both `dev-platform/evals/` and `template/dev-platform/evals/` evaluates against its descriptor with the fixture runtime
- **AND** the add-intents fixture evaluates successfully

#### Scenario: Source and template fixtures diverge
- **WHEN** a fixture file differs in content, or exists in only one of the two trees
- **THEN** the regression check fails naming the fixture
- **AND** no fixture is skipped or silently repaired
