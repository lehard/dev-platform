## 1. Complete comment history

- [x] 1.1 Update `publication_queue._comments` to read `--paginate --slurp` through `_gh`, validate outer array, every page, every row (object with integer `id`) and strictly increasing ids before returning, and raise `QueueError("PR comment-history acquisition failed for #N: <cause>")` for each failure; remove the 100-row ceiling and update the stale bounded-page wording in `_transition`.
- [x] 1.2 Add regression tests in `tests/test_publication_queue.py` with a fake `gh`: 0 (`[[]]`), 99, 100, 101 and 200 comments return complete ordered history; a trusted marker on page 2 is observed by `_events`/`_latest` replay; empty body, invalid JSON, non-array outer value, non-array page, non-object row, row without integer id, duplicate/regressing id across pages, and a failing later page each raise the named error and return no prefix.

## 2. Distinct required-check observation

- [x] 2.1 Probe the real `gh pr checks` behavior against gh 2.97 (done by the executor: `--json` exits 0 for passed/pending/failed lists; `--required` with no required checks exits 1 without JSON; exit 8 only without `--json`) and record the observed shapes as test fixtures; design D2 was revised accordingly before code.
- [x] 2.2 Add `cause` to `RequiredCheckState` and one shared classification path in `publication_state.py` used by `required_check_state`, `required_check_state_for_ref` and `publication_queue.candidate_status`: resolve the required set from the final protected target (main via `--required`; `requirement/BR-<n>` bases via main's branch response `protection.required_status_checks` filtered over `gh pr checks --json` rows, missing required row = pending; other bases raise), resolve `--required` exit 1 without JSON through base branch protection (valid unprotected branch/empty required set -> not_registered, required -> malformed, API failure -> transport), map other exits to `transport` and invalid JSON to `malformed`, and re-read the PR head after the checks call (`head-mismatch`).
- [x] 2.3 Add tests in `tests/test_publication_state.py` using the fake-`gh` harness and the recorded real shapes: exit 0 passed, exit 0 IN_PROGRESS -> pending, exit 0 FAILURE -> failed, exit 0 `[]` -> not_registered, `--required` exit 1 empty stdout with a valid unprotected branch response -> not_registered, with protected base requiring checks -> unknown/malformed, protection API failure -> unknown/transport, other exit -> unknown/transport, garbage stdout -> unknown/malformed, contribution base with main requiring `validate`: success/in-progress/missing row/failure, unsupported base raises, head differing before and changing between calls -> unknown/head-mismatch; assert every `unknown` carries a cause.
- [x] 2.4 Implement the `publication_queue._integrate` mapping from design D2: pending waits non-terminally, failed raises `IntegrationRepairNeeded(gate="required-checks")`, `unknown` with cause `transport` or `head-mismatch` returns a released `waiting` result naming the cause, `malformed`/`unsupported-state` raises `QueueError`.
- [x] 2.5 Add `tests/test_publication_queue.py` cases proving a pending snapshot never produces `_block`, a failed snapshot enters the bounded integration repair, transport and head-mismatch return waiting with the cause in the reason, malformed output still blocks visibly, and a contribution PR to `requirement/BR-<n>` records a passed required-checks gate from main's `validate` check; pin `project_publish.wait_for_pr_checks` / `finish_task` / `rollout_preflight` against the recorded real shapes.

## 3. Fail-closed trust configuration

- [x] 3.1 Remove the `except Exception: continue` from `publication_queue.trusted_apps`; read env, platform config and operator config under their explicit contracts, treat only documented absence as valid, and raise `QueueError("trust source <name> is unreadable or invalid: <cause>")` naming the source for an unparseable platform config, a missing/invalid enabled operator config, a non-table `[publication]` or a non-string `coordinator_app`.
- [x] 3.2 Add tests in `tests/test_publication_queue.py` with real temp config files: valid platform and operator values are unioned with the env name; no config / operator disabled / no `[publication]` yields only the env name (or an empty set); invalid TOML, an enabled-but-missing operator config, non-table `[publication]` and non-string `coordinator_app` each raise naming the source; a caller from the admission path and one from the worker path (`lifecycle_workers._coordinator_trust`) fail instead of continuing with a narrowed set.

## 4. Managed provenance without quick-task downgrade

- [x] 4.1 Verify the managed predicate (task-state file present, or exact head touching `openspec/changes/`) against a real managed fixture and a quick-task fixture; update design D4 first if it misclassifies either.
- [x] 4.2 Rewrite `_admission_handoff` to apply the managed predicate, require checkout at the admitted head and a `content_identity` proof with a non-empty digest for managed candidates, raise `QueueError("managed candidate <branch> lacks valid exact task-content provenance: <cause>")` otherwise, stop using `agent_friction.current_task_content`, raise on `rev-parse`/git failures, and keep the `{"branch","head"}` identity only for genuine quick tasks. Make `_archived_verification_gate` raise on unreadable state or malformed evidence while still returning no gate when no archived evidence exists.
- [x] 4.3 Audit `_integrate`/`_transition` identity inheritance for a reachable branch/head downgrade of a managed record; add a regression test either way (preserved managed identity, or the fix).
- [x] 4.4 Replace `test_admission_identity_is_the_task_content_digest_when_proven` and add tests: managed with valid proof binds the task-content digest and archived-verification gate; managed with unreadable/invalid state, checkout at another head, `content_identity` returning `None`, or empty digest raises and writes no admission; unreadable/malformed archived evidence raises; no archived evidence yields no gate; a genuine quick task still gets branch/head identity; a developer handoff with supplied identity is unchanged.

## 5. Parity and verification

- [x] 5.1 Confirm `scripts/` shims and the rendered template use the changed `template/scripts` implementation; add or extend the template contract/render test only if a shipped file list or hash changes.
- [x] 5.2 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 scripts/run_test_groups.py --all` and `python3 template/scripts/openspec_lifecycle.py check`.
- [x] 5.3 Run semantic OpenSpec verification of every delta scenario; record actual commands, results and limitations (reported-not-changed items from design.md) truthfully in verification.md.

## 6. Complete delivery

- [x] 6.1 Resolve the developer friction checkpoint and publish through the managed lifecycle.
- [x] 6.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.

## Review repairs

- [x] Validate archived verification gate fields before admission, including unsuccessful evidence; regress missing checkout, malformed digest/head and outcome.
- [x] Read required-check protection through the Contents-readable branch endpoint; regress coordinator permission containment and malformed/missing branch observations while retaining App bindings.
