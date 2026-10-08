## 1. Worker identity

- [x] 1.1 Add `resolve_worker_identity` and the shared identity validator in `template/scripts/lifecycle_workers.py`; resolve once in `main`, print `worker` in the result JSON and exit 2 on an invalid explicit identity before any GitHub call.
- [x] 1.2 Validate in `claim_body` and `result_body`; remove every `worker="worker"` default (`execute_job`, `pr_review_gate.run_claimed`, `integration_contour.run_claimed_integration_repair`, other executors) and update in-tree callers.
- [x] 1.3 Keep `i_won`/`winning_claim` exact-string replay so earlier identities remain valid on read.

## 2. Originating repair provider

- [x] 2.1 Add `model_routing.read_route_for_change` (change-keyed durable record, provenance validation, supported provider, explicit `RoutingError`).
- [x] 2.2 Persist `route` on the developer handoff in `publication_queue.admit`/`_transition` and surface it from `candidate_lifecycle.derive_candidate` as an additive field; inherit it across head changes and reject a change switch without a handoff route. Rebase on the publication-observation child before editing shared parse code.
- [x] 2.5 Amend provider authorization for recorded operator re-offers (`authorized_repair_providers`, `publish_job(reoffer=)`, `select_job` per-candidate check) with tests; keep exactly one provider per repair job.
- [x] 2.3 Resolve repair, integration-repair and default review providers from the candidate record in `publish_job`; delete the `unresolved-originating-task-route` sentinel, its friction emission and the sentinel defaults in `pr_review_gate.offer`, `complete_review` and `run_claimed`; reject contradictory or unsupported provider data with a named error; confirm each coordinator-side call site propagates the error.
- [x] 2.4 Add `work-next --provider`, make it required for repair kinds, filter by provider in `select_job` with the `unauthorized` report, carry `provider` in claim and result bodies and re-verify it in the repair executors before running.

## 3. Project check runtime

- [x] 3.1 Add `project_check_env` (purpose `project-check`) to `_platform_common.py` (imported by `lifecycle_workers.py`; kept outside the coordinator stack so portable Requirement full checks never import it), built on `credential_free_env`, with granted home-path symlinks and the always-refused credential rules.
- [x] 3.2 Add runtime declaration parsing and grant-file validation to `template/scripts/requirement_integration.py`; make `_run_full_checks` build the environment once and fail before the first command on any unmet requirement.
- [x] 3.3 Document the `[runtime]` table and `DEV_PLATFORM_PROJECT_RUNTIME_FILE` in the shipped `template/dev-platform/checks.toml` comments and the relevant docs/engineering page; keep `scripts/` shims and template render in parity.
- [x] 3.4 Confirm `run_llm`, `harness_git`, `harness_push_env` and finalization environments are untouched.

## 4. Regression tests

- [x] 4.1 `tests/test_lifecycle_workers.py`: distinct identities across host, pid and nonce; explicit precedence; invalid explicit values (empty, too long, whitespace, slash) fail with nothing posted; claim, result and CLI worker equal; old `worker-123` claims replay; missing `worker` argument fails.
- [x] 4.2 `tests/test_lifecycle_workers.py`, `tests/test_publication_queue.py`, `tests/test_pr_review_gate.py`, `tests/test_autonomous_integration_contour.py`: handoff records route; coordinator-side repair/integration-repair inherits it from another checkout; missing route, unsupported provider, provider/providers contradiction, change switch without route all fail and publish no job; no sentinel or `fallback` friction; explicit review providers list still ordered; repair kinds without `--provider` fail; mismatched worker reported unauthorized with no claim comment; matching worker records provider in claim and result.
- [x] 4.3 Routing test module: `read_route_for_change` success, missing, unreadable, change mismatch and unsupported provider.
- [x] 4.4 `tests/test_requirement_integration.py` and `tests/test_requirement_contribution_composition.py`: replace the scratch-HOME assertion test; cover declared tools/env/granted home path success, no declaration unchanged, missing tool, missing env, ungranted path, unset and in-checkout grant file, forbidden and traversal paths, credential-named `required_env`, failure before the first command, and unchanged LLM/harness environments.
- [x] 4.5 Rendered downstream fixture with a `[runtime]` declaration parsed through installed shims.

## 5. Verify

- [x] 5.1 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 scripts/run_test_groups.py --all` and `python3 template/scripts/openspec_lifecycle.py check`.
- [x] 5.2 Run semantic OpenSpec verification for every delta scenario and write a truthful `verification.md` naming the commands and methods actually used and any limitation (no real multi-host dogfood).

## 6. Complete delivery

- [x] 6.1 Resolve the developer friction checkpoint and publish through the managed lifecycle.
- [x] 6.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.
