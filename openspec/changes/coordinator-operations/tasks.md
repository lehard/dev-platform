## 1. Coordinator preflight

- [x] 1.1 Consume the strict `trusted_apps` reader and complete comment reader from `publication-observation`; confirm both are merged before starting and update design first if their signatures differ from this design.
- [x] 1.2 Implement `publication_queue.preflight(root, mode, phase, env)` and the `preflight --mode ci|local --phase inputs|runtime|all` subcommand (both flags required): input flags, run context, tool availability, App identity and contradiction check, strict trust read, `enabled`/`_repo` agreement, token scope and permission probes with fixed failure categories; first failure stops, names the input, exits 2.
- [x] 1.3 Make `worker` require `--mode`, run the full preflight before `_repo`/`_queued`, and return the preflight error result without observing any candidate.
- [x] 1.4 Update `.github/workflows/publication-queue.yml`: `Preflight inputs` step before the token step with boolean presence env from `vars`/`secrets` expressions, `Preflight runtime` after it, `worker --mode ci`; keep permissions and base-branch-only checkout unchanged. Update `docs/engineering/agent-workflow.md` and `docs/managed-rollout.md` for the preflight and the new `worker --mode` invocation.

## 2. Durable coordinator evidence

- [x] 2.1 Add the `evidence:v1` record builder/parser and trusted reader in `publication_queue.py`, with named errors for malformed, mismatched-PR/head or incomplete trusted records and idempotent posting by `dedupe_key` using the complete history reader.
- [x] 2.2 Resolve one worker run identity in `worker()` (CI run ids; local host/pid/uuid generated at start), require it in `use_default_friction_sink` and `emit_friction`, and pass `--worker` from `lifecycle_workers.work-next`.
- [x] 2.3 Rewrite `integration_contour.default_friction_sink` as durable-first then local mirror; add optional deterministic `event_id` to `agent_friction.append_coordinator_event` keeping existing uuid behavior for other callers.
- [x] 2.4 Implement `publication_queue.requirement_evidence` (extract the candidate-PR inventory helper from `requirement_status` without changing its output) and merge durable events into `agent_friction.events_for_task` for Requirement refs; extend `_check_events`, `evidence_source_status(requirement=...)` and `requirement_retrospective review-path` output with durable provenance and the `coordinator-evidence` source.

## 3. Verify behavior

- [x] 3.1 Preflight regression tests (new `tests/test_coordinator_preflight.py` plus workflow assertions in `tests/test_candidate_lifecycle.py`): all-valid ci and local; each missing flag/run id/tool; empty App slug; env versus configured slug contradiction; unreadable trust configuration (named reader error); `enabled` false; repo mismatch; token not an installation token for the repository; insufficient bot permission; unauthorized/unreachable categories; canary secret never in any output; `worker` without `--mode` is a usage error and a failing preflight never calls `_queued`; workflow step order and permission inputs.
- [x] 3.2 Durable evidence regression tests (`tests/test_publication_queue.py`, `tests/test_autonomous_integration_contour.py`, `tests/test_requirement_retrospective.py`, `tests/test_retrospective_attribution.py`): record round-trip with Requirement/head/stage/worker; retry posts once; forged-author record ignored; malformed trusted record raises; comment-post failure raises before the handoff record is posted and `worker` exits 2; local mirror failure raises; review-path on a checkout with an empty local log lists durable events with provenance; checkpoint requires linking a durable high-severity or workaround event; unreadable durable source is a named gap refused unless `--accept-gap`; developer task retrospectives never call GitHub.
- [ ] 3.3 Run source and rendered-template checks (`python3 -m compileall -q template/scripts scripts`, `python3 scripts/run_test_groups.py --all`, `python3 template/scripts/openspec_lifecycle.py check`), confirm `scripts/*` shims and template parity, run semantic OpenSpec verification and write truthful `verification.md` stating what was and was not checked (no real App token probe).

## 4. Deliver through managed lifecycle

- [ ] 4.1 Resolve the developer friction checkpoint and publish through the authoritative managed lifecycle.
- [ ] 4.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.
