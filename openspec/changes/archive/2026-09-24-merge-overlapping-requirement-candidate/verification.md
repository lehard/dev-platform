OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of exact-parent manifest, preparation, conflict bounds, finalized merge history, full validation and protected publication against proposal, design and specification; Git-backed success/refusal tests and strict OpenSpec validation.
Automated-Checks-Evidence: automated-checks.json
Requirement-Integration-Exception: Publish this merge recovery capability independently so the overlapping archived children of Requirement #164 can be integrated on current main through one protected candidate.

Outcome: An exact sequential child chain can be merged from current main in an isolated generation, with conflict resolution bounded to child-touched overlap paths, exact two-parent history, content-bound manifest and unchanged terminal publication authority. Previous candidates and child branches remain untouched.
Evidence: `python3 -m unittest` targeted merge tests (2 passed); `python3 -m ruff check scripts template/scripts tests` (passed); `python3 -m compileall -q template/scripts scripts` (passed); `python3 scripts/managed_projects.py validate` (passed); `python3 scripts/run_test_groups.py --all` (13 groups passed, 1275 tests discovered); `openspec validate merge-overlapping-requirement-candidate --strict` (valid). Archive helper will execute applicable checks again and record exact checkout evidence.
Limit: The real #164 conflict resolution, combined candidate validation, exact merged PR and terminal board reconciliation follow after this recovery capability is merged; this receipt does not claim them complete.
