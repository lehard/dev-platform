## 1. Confirm current runtime contract

- [x] 1.1 Reproduce/document the Codex temp-root writable behavior on the currently supported runtime(s) and identify only the extra writable roots that can be proven.
- [x] 1.2 Compare current `delegated_write_guard.py` behavior and canonical `platform-delegation` spec against that evidence before changing semantics.

## 2. Harden capability classification

- [x] 2.1 Add a small normalized topology model for protected repository paths and known runtime-added writable temp roots.
- [x] 2.2 Make Codex `HARD` classification depend on both sandbox capability and safe repository topology.
- [x] 2.3 Make `require_hard=True` fail closed before launch when topology overlaps a runtime-writable temp root.
- [x] 2.4 Preserve explicit `DETECTION_ONLY` downgrade plus its existing dirty-integration refusal when hard is optional.
- [x] 2.5 Keep the content-aware post-check enabled for hard runs.

## 3. Regression coverage

- [x] 3.1 Test normal repository/worktree outside temp roots -> `HARD` when the runtime capability is available.
- [x] 3.2 Test integration repository under `/tmp` -> no `HARD`.
- [x] 3.3 Test active/custom `$TMPDIR` overlap -> no `HARD`.
- [x] 3.4 Test symlink/realpath overlap into a temp root -> no false `HARD`.
- [x] 3.5 Test `require_hard=True` blocks before child execution in unsafe topology.
- [x] 3.6 Test optional downgrade remains detection-only and refuses dirty integration state.
- [x] 3.7 Reproduce the original live-acceptance edge case so future changes cannot reintroduce misleading tier/reporting.

## 4. Contract, validation and release

- [x] 4.1 Update canonical/generated guidance only where necessary to describe `HARD` accurately.
- [x] 4.2 Run the full applicable platform validation contract, including delegation tests, template/render/Copier smoke, OpenSpec lifecycle and strict semantic validation.
- [x] 4.3 Perform a real guarded Codex acceptance covering one safe normal topology and one temp-root unsafe topology; record the actual runtime/version/evidence.
- [x] 4.4 Record truthful `OpenSpec-Verify: PASS`, archive through the lifecycle helper and publish through protected main.
- [x] 4.5 Include runtime/template changes in the next normal immutable platform release; do not cut a release solely for archive/spec bookkeeping.

## Explicitly out of scope

- Claude shell/structured-write redesign.
- New OS sandbox implementation.
- Global `/tmp` prohibition.
- Publication, rollout, gh-aw/friction or Development Backlog changes.
