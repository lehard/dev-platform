OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of explicit shared-manifest identity, ordinary managed publication isolation, exact committed candidate checks and protected PR gates against proposal/design/spec; targeted Git-backed and publisher refusal tests; strict OpenSpec validation.
Automated-Checks-Evidence: automated-checks.json
Requirement-Integration-Exception: Publish this shared publisher correction independently so the already-open combined #164 PR can finish without misattributing its three children to one Issue.

Outcome: A valid shared candidate skips only the ordinary one-child In review Project update; protected checks, merge guard and exact merged-PR terminal reconciliation remain mandatory. An invalid shared manifest stops before feature push or PR mutation.
Evidence: `python3 -m unittest` three targeted shared-publication tests (passed); `python3 -m ruff check scripts template/scripts tests` (passed); `openspec validate publish-shared-requirement-pr --strict` (valid). Archive helper will execute applicable full checks on the exact committed checkout and record them in `automated-checks.json`.
Limit: PR #106 and #164 are not claimed complete by this receipt; they require separate exact-head protected merge and terminal reconciliation after this tool is published.
