# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/spec deltas against the diff, plus targeted unit tests and the full test-group run
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Local worker observe-only: `publication_queue.run_worker` returns `state=error` with `LOCAL_WORKER_REFUSAL` for `mode == "local"` before preflight, run identity, friction sink or any GitHub read; the reason names the CI `publication-queue` workflow (coordinator App) as the only integrator and points to `publication_queue.py status` and `preflight --mode local --phase all`. CLI `worker --mode local` exits 2 with that JSON. `run_identity` now only builds the CI identity (the local branch was unreachable).
- Local preflight: the `repository-permission` push probe is removed from `_preflight_runtime`; local inputs (tools, `gh auth status`), App identity, trust configuration, enabled coordinator, repository and pull-request read remain fail-explicit. CI branch unchanged.
- Harness push credential: `lifecycle_workers.active_gh_token` runs `gh auth token` (prompt disabled, stdin closed, output captured) with the push environment; gh's precedence uses an exported `GH_TOKEN` (CI App token) or the operator login. Failure or empty output raises `harness GitHub push requires an authenticated gh credential (gh auth token failed)` without echoing gh output. No second credential path in platform code. The token is still only in the push process `http.<origin>.extraheader` env config; `file://`/local origins need no credential.
- Docs: `docs/engineering/agent-workflow.md` replaces the local worker retry advice with the CI-only integrator statement and the local diagnostic commands. No other doc recommended a local worker run.
- Spec deltas: `publication-queue` adds "Local coordinator run is observe-only" (scenarios: local run does not integrate; diagnostics without App token); `lifecycle-workers` adds "Harness candidate push uses the active gh credential".
- Out of scope and not done here: the GitHub ruleset on `main` (operator step of the parent Requirement after merge, with explicit owner confirmation); downstream projects.

## Checks actually run

- Targeted: `tests/test_coordinator_preflight.py` (new: local worker observe-only incl. CLI exit 2 and no preflight/worker/gh/sink calls; local preflight passes without push permission; only CI has a run identity), `tests/test_lifecycle_workers.py` (new: push credential is gh's active token — operator login without `GH_TOKEN`, exported `GH_TOKEN` preferred by gh, failure names the gh credential and does not leak gh stderr; existing secret-safety test runs through a fake `gh`), `tests/test_requirement_contribution_composition.py` (push auth test adapted; missing-credential error does not contain the token) — all pass.
- Full: `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 scripts/run_test_groups.py --all` (17/17 groups success, 3054 tests), `python3 template/scripts/openspec_lifecycle.py check` (OK).
- Real `gh` 2.97.0: `GH_TOKEN=<dummy> gh auth token` prints the exported value, confirming the precedence the design relies on.
- Authoritative selected-check evidence: `automated-checks.json`.

## Limitations

- A real local `execute_requirement.py advance` push without exported `GH_TOKEN` is exercised by this task's own publication, not by a unit test against GitHub.
- The routing record carries an owner-approved supervisor-written diff (the delegated-child executor was not opened before writing).
