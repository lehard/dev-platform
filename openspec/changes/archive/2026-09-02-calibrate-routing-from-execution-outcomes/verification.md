# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) against proposal/design/delta spec plus the full local platform test and validation matrix, and inspection of the first real `routing-calibration` report
Automated-Checks-Evidence: automated-checks.json

## Automated validation

Run locally on branch `agent/calibrate-routing-from-execution-outcomes`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — OK (13 groups, exit 0)
- `python3 template/scripts/openspec_lifecycle.py check` — OK (lifecycle hygiene OK)
- `openspec validate calibrate-routing-from-execution-outcomes --strict` — valid

New regression coverage (`tests/test_model_routing.py::RoutingCalibrationTests`, 12 cases):

- `test_small_real_sample_is_insufficient_but_still_reported` — a below-threshold
  usable sample still renders full counts and yields
  `insufficient evidence / no policy change`.
- `test_authored_r2_success_without_escalation_is_positive_evidence` /
  `test_r2_escalation_then_success_keeps_both_paths_and_reason` /
  `test_escalation_without_recorded_reason_stays_unknown` — verified authored-R2
  completion without escalation is counted as its own positive signal; an
  `R2 -> R3 -> success` path keeps both the balanced attempt and the final
  success and only reports a reason the record actually carries.
- `test_direct_r3_success_is_not_labelled_over_routed` — a direct authored-R3
  success is recorded as such, is not an R2 observation, and carries the
  explicit no-counterfactual note.
- `test_abnormal_and_unknown_outcomes_are_not_folded_into_success_or_failure` —
  `abnormal`/`unknown` stay distinct outcome buckets.
- `test_planned_only_and_unverified_records_are_excluded_from_usable` /
  `test_missing_metadata_stays_unknown_not_defaulted` — planned-only,
  unverified, and legacy (no authored tier) records drop out of the usable set;
  absent `task_family`/`rubric_version` render as `unknown`.
- `test_breakdowns_carry_counts_and_mixed_generations_are_not_merged` — each
  `task_family` / `rubric_version` / `provider:model` breakdown carries its own
  count and `adequacy`; incompatible model generations are not merged.
- `test_adequate_low_escalation_sample_yields_no_change_candidate` /
  `test_adequate_high_escalation_sample_yields_review_candidate` — an adequate
  sample produces a concrete `no change` or `review:` candidate, still flagged
  `requires_separate_managed_change`.
- `test_cli_routing_calibration_emits_json` — the new subcommand is wired and
  emits the schema-versioned payload.

## First real calibration report (task deliverable)

`python3 scripts/model_routing.py routing-calibration` against the currently
accumulated real routing records:

- 16 routing records; 10 launched; 15 verification-passed; **10 usable
  observations** → `adequacy: insufficient` (guideline 15).
- Authored tier distribution: `R2` 15, `R3` 1. Usable observations are all
  authored `R2`; `frontier_exposure_usable` 0.
- `authored_r2_verified_success_without_escalation`: 4.
- `r2_to_r3_escalation`: 0 among usable; 1 record total, with a truthfully
  recorded reason (standard Codex executor unresponsive → supervisor retained
  the diff); `success_after_escalation` 0.
- `direct_frontier`: 1 authored-`R3` record, not launched, 0 verified success —
  no over-routing / counterfactual claim.
- Outcomes over usable: completed 4, abnormal 2, failed 1, unknown 3.

**Candidate decision: `insufficient evidence / no policy change`.** More verified
managed executions must accumulate before the R2/R3 rubric, hard triggers or
model mapping are reviewed. This matches the activation decision in the source
issue: the report layer is delivered now and is not blocked by the small sample.

## Semantic review

Completeness: PASS. All five delta requirements are implemented in
`template/scripts/model_routing.py`:

- *Reuses the existing evidence path* — `routing_calibration` calls
  `_local_routing_records`, `_verification_outcome`, `_verification_roots` and
  `_runtime_identity`; it adds no store, scanner, tracing backend or state
  machine. Eligibility (`_calibration_slice` "usable" filter) needs a launched
  execution, a passed verification receipt and a known authored tier, and never
  inspects `execution.efficiency`, so a verified execution with no comparable
  token/request usage still contributes (Requirement 1 scenario).
- *Authored vs actual* — `_actual_route_of` derives the actual path from
  `escalations` + `freshness` + final `profile`; `_authored_tier_of` and
  `_managed_receipt_for_change` preserve authored tier / task family / rubric
  where present and return `unknown` otherwise. Authored-R2 clean success,
  escalated-then-success and legacy/partial records are each handled by their
  own branch (Requirement 2 scenarios).
- *No counterfactual claims* — `direct_frontier` records authored-R3 executions
  with a fixed `counterfactual_note`; the advice branches never assert R2 would
  have failed and never label a direct R3 as over-routed (Requirement 3
  scenario).
- *Sample adequacy and tradeoffs* — `sample` and `global` always carry counts
  and coverage; `global` includes authored tier distribution + frontier
  exposure, verified R2 success without escalation, escalation counts / recorded
  reasons / success-after-escalation, direct-frontier, and the distinct outcome
  buckets. `first_pass_verification` / `human_intervention` are reported under
  `unavailable_signals` because no record field proves them. `_breakdown`
  attaches a per-slice count and `adequacy`, so a usable global sample can
  coexist with an `insufficient` family, and an inadequate current sample
  returns `insufficient evidence / no policy change` without blocking the report
  (Requirement 4 scenarios).
- *Advisory only* — `_calibration_advice` returns a human-readable
  `candidate_decision` and always sets `requires_separate_managed_change: true`.
  Nothing in the module writes `start_tier_routing.py`, `.dev-platform.toml`,
  the rubric, the model mapping, a Development Backlog task, or a learned router
  (Requirement 5 scenarios).

Correctness: PASS. Run against real records the report is internally consistent
(10 usable = 4 completed + 2 abnormal + 1 failed + 3 unknown; escalation and
direct-frontier tallies match the underlying JSON) and the deliberately looser
efficiency-comparability rule means all 10 launched+verified R2 executions are
usable even though `efficiency-baseline` still reports `insufficient` for
token/request comparability. The 12 regression fixtures exercise every branch,
including the adequate-sample advice paths that real data cannot yet reach.

Coherence: PASS. `docs/engineering/model-routing.md` gains a "Routing
calibration" section describing the same surface, semantics and advisory
boundary; `design.md` "Suggested surface" (`routing-calibration` subcommand
under `model_routing.py`) is exactly what shipped. The command sits beside
`efficiency-baseline` in `main()` and prints JSON like every other subcommand.

## Scope boundary

No second execution/telemetry store, tracing backend, ML/classifier/embeddings,
counterfactual replay, human-scoring surface, dashboard, `R1` handling, or
automatic policy/managed-task mutation was added, per the accepted change
boundary. `efficiency-baseline` is reused, not duplicated.
