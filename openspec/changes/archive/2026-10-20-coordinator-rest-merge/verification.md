# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/spec delta against the diff, plus targeted unit tests and selected checks
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Merge call: `publication_queue._integrate` now runs `gh api -X PUT repos/{repo}/pulls/{number}/merge -f merge_method=squash -f sha=<head>` with the same subprocess kwargs; the expected-head guard is the REST `sha` field (GitHub returns 409 on a moved head). The read-back of `merged`, the `merged` transition and the waiting reasons (`protected merge refused; will re-evaluate: …`, `merge accepted; awaiting GitHub confirmation`) are unchanged. No retry, `--admin`, `--auto` or alternate merge path was added.
- GitHub now evaluates rules, ruleset bypass and required checks itself; gh's client-side `mergeStateStatus=BLOCKED` pre-check (the cause of the 2026-10-20 queue refusals of #647) is no longer on the path.
- Unchanged by design: `project_publish.py` (non-coordinator project publication) and the pre-existing `except QueueError: pass` after a successful merge (reported to the owner as a pre-existing swallowed error).
- Test harness: `parallel_lifecycle_acceptance.LocalGitHub` gains a `PUT pulls/N/merge` route (squash only, `sha` as expected head) sharing the squash-merge logic with the legacy `pr merge` route, because the acceptance test drives `queue.worker`.

## Checks actually run

- Delegated executor (Claude, recorded with `record-claude-execution`): `python3 -m pytest -q tests/test_publication_queue.py tests/test_autonomous_integration_contour.py tests/test_coordinator_preflight.py tests/test_parallel_lifecycle_acceptance.py` — 201 passed; `ruff check template/scripts tests` passed; manifest regenerated. New test: protected-ref 405 refusal yields `waiting` with the bounded reason, no block and no merged transition; exact REST argv with `sha=HEAD` asserted.
- Supervisor: reviewed the diff; selected checks recorded in `automated-checks.json`.

## Limitations

- That GitHub applies the ruleset `pull_request` bypass for the App on this endpoint is not provable without the App token locally; the parent Requirement's operator step re-enables ruleset 25455693 after this merges and observes a real queue merge, rolling back on refusal.
