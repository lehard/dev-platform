# Verification: add-harness-replay-lab

OpenSpec-Verify: PASS

Verification-Method: Manual semantic comparison of the accepted Issue and active proposal, design, tasks and delta specification against the implemented replay suite, evaluator, controlled fixtures, documentation and focused tests; strict OpenSpec validation and full platform checks.

Automated-Checks-Evidence: automated-checks.json

## Outcome and scope

- Five frozen cases pin exact source revisions, historical OpenSpec proposal/spec files, successful verification receipts and automated-checks receipts. The validator checks their Git object content hashes and case/suite digests; the source revisions are ancestors of their accepted archive revisions.
- A disposable detached repository is materialized for each case. The lab executes no arbitrary candidate command. Candidate execution and independent outcome verification remain the responsibility of a separate isolated runner; reports label those supplied observations and do not promote them to a positive optimization conclusion. This boundary is explicit in the design and operating guide.
- The native historical control reuses pinned successful check receipts and compares check wall time at zero delta. Missing token, cache, cost, intervention and incompatible payload evidence remain unknown.
- The controlled failure fixture demonstrates that a purported saving with failed verification is rejected before efficiency ranking. The unreviewed-candidate test demonstrates that a negative numeric delta supplied by a candidate remains advisory.
- The report writes no routing, context, runtime, release or backlog state.

## Checks performed

- `python3 -m unittest tests.test_harness_replay -v`: 6 passed after the final changes.
- `python3 scripts/run_test_groups.py --all`: passed 13 groups, 1409 declared and discovered tests, with no coverage gaps after the final changes.
- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 scripts/managed_projects.py validate`: passed, 3 managed projects.
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `python3 -m ruff check scripts template/scripts tests`: passed.
- `openspec validate add-harness-replay-lab --strict --no-interactive`: passed.
- `git diff --check`: passed.

## Semantic review

- **Completeness:** The small suite, exact historical identity, independent reference receipts, frozen drift gate, ordered capability and efficiency gates, visible unknowns, controlled candidate families and advisory output are implemented and tested.
- **Correctness:** External candidate verification fields are provisional supplied observations, not established ground truth. Their numeric claims may be displayed for review but cannot produce a positive optimization conclusion without independent assessment. Historical control values are checked against pinned receipts.
- **Coherence:** The implementation follows the bounded evidence-ingestion design and leaves the narrow #104 calibration and provider-specific pilots separate.

The archive helper will generate `automated-checks.json` for the exact archive candidate. The marker above names that expected evidence, not a pre-existing result.
