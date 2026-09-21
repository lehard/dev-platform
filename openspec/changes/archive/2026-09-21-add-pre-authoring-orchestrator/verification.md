# Verification: Resumable pre-authoring orchestrator

## Method

`/opsx:verify` was not available in this execution environment (no OpenSpec-provided
Claude/Codex skill registered in this session). Performed the documented equivalent
manual OpenSpec semantic review instead: re-read `proposal.md`'s Why/What
Changes/Success Evidence, `design.md`'s stage graph/human-decision
protocol/failure behavior, and the `agent-workflow` spec delta's four ADDED
requirements with their scenarios, then checked the implementation
(`template/scripts/orchestrate_pre_authoring.py`) and its test suite
(`tests/test_orchestrate_pre_authoring.py`) against each one individually.

## Outcome / success evidence review

- "A representative flow can pause for a human decision or process restart and
  resume without rebuilding fresh upstream stages" — `test_clean_run_reaches_complete_handoff`
  drives the full snapshot -> ADD -> intents -> handoff path; `test_human_pause_surfaces_open_decision_and_resume_applies_the_answer`
  drives the pause/resume path; `test_resume_after_restart_does_not_repeat_fresh_worker_extraction`
  asserts a second `status()` call (a fresh process would behave identically,
  since status recomputes only from the artifact files on disk) returns the
  exact same snapshot stage result without any new worker input.
- "mutation of an upstream artifact invalidates only dependent downstream
  stages" — `test_upstream_mutation_invalidates_only_dependent_downstream_stage`
  mutates a tracked snapshot source after the ADD was approved and confirms
  `status()` stops at the snapshot stage (now stale) rather than trusting the
  already-approved ADD/evidence link built from the old snapshot.
- "failures/escalations preserve state" — `test_stage_failure_is_reported_and_recoverable_without_touching_upstream`
  introduces a dependency cycle in the intent set and confirms the ADD stage
  (upstream, still fresh) is unaffected and untouched; repairing only the
  intent set resumes correctly.
- "no new backlog/status/source-of-truth lifecycle appears" —
  `test_orchestrator_creates_no_competing_status_or_priority_fields` asserts the
  receipt contains no backlog-shaped field (`status`/`priority`/`assignee`/`project_number`).
  The module never writes to the Development Backlog Project, GitHub, or the
  managed-task lifecycle; it only reads/writes files under
  `.claude/pre-authoring/<id>/`, which is machine-local and git-ignored
  (`.claude/` is ignored repository-wide).

## Spec-delta scenario review (`specs/agent-workflow/spec.md` in this change)

- "Fresh end-to-end pre-authoring run" — `test_clean_run_reaches_complete_handoff`.
- "Completed upstream stage remains fresh" — `test_resume_after_restart_does_not_repeat_fresh_worker_extraction`.
- "Upstream content changes" — `test_upstream_mutation_invalidates_only_dependent_downstream_stage`.
- "ADD worker needs a material choice" / "No human choice is needed" —
  `test_human_pause_surfaces_open_decision_and_resume_applies_the_answer` (decision path);
  `test_clean_run_reaches_complete_handoff` (no-choice path: an ADD with an empty
  `unresolved_choices` list proceeds straight to `needs-approval`).
- "Run receipt is present" — every `status()` call writes `receipt.json`; the
  clean-run test reads it back and asserts it names no raw prompt/transcript content.
- "Snapshot extraction is routine" — `test_snapshot_needing_extraction_surfaces_worker_requests`
  confirms the orchestrator surfaces `project_evidence.py`'s own `worker_request`
  contract unchanged (routine/read-only worker path), rather than defining a
  competing one.
- "Design stage needs stronger reasoning" (routing escalation) — verified by
  code inspection rather than a dedicated behavioral test: `orchestrate_pre_authoring.py`
  contains no retry loop, scheduler, or routing decision of its own: it forwards
  every substantive drafting/decomposition step to the calling agent as a
  bounded `action` string, and escalation is therefore necessarily handled by
  the existing `scripts/dogfood_task.py route-claude`/`route-codex` contract
  the calling agent already uses, not by a new implementation here. Noted
  explicitly as a design-level (absence-of-implementation) property rather
  than claiming a positive escalation test exists.

## Correctness / coherence

Read `template/scripts/project_evidence.py` and `template/scripts/add_intents.py`
in full before writing this change. The orchestrator calls their public
functions (`build_snapshot`, `validate_snapshot`, `validate_add`, `decompose`,
`validate_intents`, `check_handoff_staleness`) directly for every
freshness/staleness/coverage/digest-binding decision; it duplicates none of
that logic. `record_decision` writes then re-validates through `add_intents.validate_add`
(public API) and rolls back the write on failure, so it cannot persist a
document that fails the same structural gate `approve_add` will enforce next.

## Independent review

A native Claude executor (agent_id `abf68c3997293e2a4`, recorded via
`scripts/model_routing.py record-claude-execution`) independently read the
proposal/design/spec, both composed modules, and the test suite, and ran the
tests itself. It found two real bugs, both fixed here with regression tests:

- `init()` did not retry ADD scaffolding after a prior partial failure left
  `state.json` without `add.json`, permanently wedging the requirement.
- `record_decision()`'s rollback write on a failed re-validation used a plain
  `write_text` instead of `atomic_write_text`, reintroducing the partial-write
  risk that helper exists to prevent.

Re-ran the full suite after the fixes; all groups still pass.

## Tests run

```
python3 -m compileall -q template/scripts scripts tests
python3 -m unittest tests.test_orchestrate_pre_authoring -v   # 12/12 passed
python3 scripts/run_test_groups.py --all                      # 13/13 groups, 1108/1108 tests passed
python3 template/scripts/openspec_lifecycle.py check           # OK
openspec validate add-pre-authoring-orchestrator --strict --no-interactive   # valid
```

No material finding surfaced during this review.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
