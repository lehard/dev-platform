## 1. Correct shipped metadata

- [x] 1.1 Review the BR-353 (e3484b2) diff of `dev-platform/capabilities/add-intents.md` against `add-intents-pilot.json` cases and `quality_comparisons`; record that the cases remain valid (or update any invalidated case).
- [x] 1.2 Set `content_sha256` of `add-intents-pilot.json` to the descriptor's `provenance.content_sha256` in both `dev-platform/evals/` and `template/dev-platform/evals/`.
- [x] 1.3 Make `interoperable-agent-handoff-pilot.json` byte-identical in both trees using the template placeholder prompt; confirm no other file pins its prompt digest.

## 2. Regression coverage

- [x] 2.1 Add a test in `tests/test_capability_manager.py` that evaluates every fixture in `dev-platform/evals/` and `template/dev-platform/evals/` against its descriptor with the fixture runtime and fails naming root and fixture.
- [x] 2.2 Add a parity test asserting the two trees contain the same fixture names with identical bytes.
- [x] 2.3 Add a negative case: a temporary fixture with a stale hash makes `evaluate_existing` raise the explicit hash-mismatch `CapabilityError`, and a fixture with no descriptor fails explicitly.
- [x] 2.4 Run `python3 scripts/capability_manager.py evaluate --fixture dev-platform/evals/add-intents-pilot.json add-intents` and the template equivalent; run required platform checks and semantic verification; record truthful results in verification.md.

## 3. Complete delivery

- [x] 3.1 Resolve the developer friction checkpoint and publish through the managed lifecycle.
- [x] 3.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.
