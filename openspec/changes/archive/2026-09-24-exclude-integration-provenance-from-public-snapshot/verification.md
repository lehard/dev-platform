# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the proposal, design, public-distribution delta, exact policy diff, positive and negative regression cases, and snapshot-smoke evidence.
Automated-Checks-Evidence: automated-checks.json

The implementation excludes only `dev-platform/requirement-integrations/` through the shared candidate-set function. Audit, digest and tar construction continue to use that same set. The new negative test proves that another product file carrying the same noncanonical owner reference still blocks audit and snapshot. The canonical repository allowlist and credential patterns are unchanged. This matches the authored outcome and leaves no material finding.

Executed checks before archive:

- `python3 -m unittest tests.test_public_distribution -v`: 22 tests passed.
- `python3 tests/public_distribution_snapshot_smoke.py`: passed; extracted snapshot ran all 1302 tests across 13 groups, plus compileall and lifecycle hygiene.
- `python3 scripts/managed_projects.py validate`: passed.
- `openspec validate exclude-integration-provenance-from-public-snapshot --strict`: passed.
- `git diff --check`: passed.

The shared PR's protected Linux CI and merge remain pending, and are not claimed here.
