# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual completeness/correctness/coherence review (the current agent integration did not expose `/opsx:verify`)
Automated-Checks-Evidence: automated-checks.json

## Completeness

- Selective activation is implemented in the central and rendered agent contracts: explicit goal-backed work and materially fuzzy non-trivial intake are covered, while concrete quick and implementation tasks remain direct.
- The quality bar includes outcome, verification evidence, a quantitative or binary threshold, scope bounds, and a clarification stop.
- Native `/goal` or runtime-native goal state is limited to explicit goal-backed requests. Fuzzy managed intake remains transient, and unsupported environments cannot claim `create_goal` or active-goal success.
- Goal refinement creates no durable authoring artifact; managed Issue/OpenSpec provenance remains authoritative.
- Model-specific critic routing is not introduced, and existing model-routing/delegation rules are unchanged.

## Correctness

- Preflight inspected the current curated `define-goal` skill and official OpenAI `/goal` guidance. `codex-cli 0.135.0` reported the stable `goals` feature enabled.
- `python3 -m unittest discover -s tests -v` passed through `scripts/select_checks.py --execute` (240.091 seconds).
- The focused goal-definition and managed-intake contract tests passed after the final contract clarification.
- `openspec validate adopt-define-goal-intake --strict` passed.
- A working-tree Copier render with the repository-tested `copier==9.17.0` produced the expected `AGENTS.md` and workflow guidance; the rendered doctor compiled successfully.
- `python3 template/scripts/openspec_lifecycle.py check` reported `OpenSpec lifecycle hygiene: OK`.

## Coherence

- The implementation uses the existing AGENTS/Copier distribution path and does not vendor external skill content or add a runtime adapter.
- The native/transient boundary is coherent with both official durable `/goal` behavior and the platform rule against a competing goal artifact.
- The change preserves the accepted managed-task intake contract and does not overlap the active `adopt-gh-aw-process-automation` change.

No material semantic findings remain.
