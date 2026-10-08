## Why

A shipped eval fixture binds to a capability by `content_sha256`, and `capability_manager.evaluate_existing` refuses a mismatch. The `add-intents` fixture hash (6e3c711b...) has been stale since BR-353 changed the descriptor/instructions (b3889d76...), so the documented direct eval path fails in source and in every downstream project that receives the template. No check evaluates fixtures, so the drift reached main unnoticed and would reach the stable release. The `interoperable-agent-handoff` fixture additionally differs between source and template.

## What Changes

- Re-baseline `add-intents-pilot.json` `content_sha256` to the current descriptor hash in `dev-platform/evals/` and `template/dev-platform/evals/`, after reviewing that the BR-353 instruction edits do not invalidate the fixture's trigger cases.
- Make `interoperable-agent-handoff-pilot.json` byte-identical in both trees (use the source `example/development-backlog#123` prompt text only if the digest-bound cases stay valid; otherwise the template text; one value, decided in design).
- Add a regression test that, for both `dev-platform/` and `template/dev-platform/`, loads every shipped eval fixture, resolves its descriptor, runs `evaluate_existing` with the fixture runtime, and asserts the two trees' eval fixture sets are identical byte for byte.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engineering-capabilities`: shipped eval fixtures must evaluate successfully against their descriptors and stay identical between source and template.

## Impact

Fixture JSON data in `dev-platform/evals/` and `template/dev-platform/evals/` (Copier-managed, so existing downstream projects receive the corrected fixtures on update) and one test in `tests/test_capability_manager.py`. No change to `capability_manager.py` behavior, CLI, descriptor schema or the `evidence` field.

## Success Criteria

- `python3 scripts/capability_manager.py evaluate --fixture dev-platform/evals/add-intents-pilot.json add-intents` succeeds, and the same succeeds against the template tree.
- Every fixture in both trees evaluates against its descriptor in the test suite; reintroducing a stale hash makes the test fail naming the fixture.
- Source and template eval fixtures are byte-identical.

## Non-goals

- Normalizing the heterogeneous `[eval].evidence` values (`none`, `deterministic-fixture`, a path); recorded as an observation, not changed, to avoid a descriptor-schema change and a content-hash churn across downstream projects.
- Adding fixture evaluation to `capability_manager.py validate`/`audit` (would make a downstream project's validate depend on fixtures it does not necessarily ship).
- Live provider evals, new capabilities, or changing eval core semantics.
