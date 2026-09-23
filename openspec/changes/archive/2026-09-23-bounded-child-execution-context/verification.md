# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual scenario-by-scenario review of the active delta against the implementation and regression tests, plus `openspec validate bounded-child-execution-context --strict`.
Automated-Checks-Evidence: automated-checks.json

The child handoff derives only the exact source Issue, active canonical package provenance, current repository HEAD, parent Requirement and explicitly supplied predecessor receipt. The derived file is ignored and disposable; no pre-authoring transcript or sibling body is copied. Start and resume refresh it, while routing rejects stale HEAD or provenance. An exact standalone parent backlink is required; authored `Parent Requirement:` prose did not satisfy this and the live #187 link was repaired. Codex routing uses the validated path in its prompt; Claude routing prints it for the native handoff.

The dedicated tests exercise bounded content, ambiguous linkage, stale dependency refresh, exact backlink repair and routing behavior. `python3 -m unittest tests.test_central_dogfood_lifecycle -q` (19 tests), `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m ruff check scripts template/scripts tests`, and `git diff --check` passed after the last implementation edit. A previous full run passed all 13 groups and 1276 tests before the final Claude handoff edit; the archive helper will rerun selected checks and write the exact automated evidence before archiving. No failure was classified as pre-existing.
