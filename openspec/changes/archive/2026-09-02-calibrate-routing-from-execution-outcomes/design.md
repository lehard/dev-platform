# Design: Thin routing calibration over the existing execution baseline

## Decisions

1. **Reuse the existing scanner and evidence path.** `model_routing.py efficiency-baseline` already scans durable routing records, separates launched from verified/eligible observations, reads active/archived verification evidence, and preserves unknown metadata. Routing calibration extends or reuses these primitives; it does not create a sibling store or scanner.

2. **Define routing eligibility separately from efficiency comparability.** The efficiency report's `sufficient` status also cares about comparable timing/usage fields. Routing calibration instead needs verified executions with enough routing facts: authored tier/rubric/task family where present, actual route/outcome, and verification evidence. Reuse the same observation set and coverage accounting, but do not require token/request comparability to reason about R2/R3 outcomes.

3. **Prefer existing facts; add no event log.** Use existing authored receipt, execution participant/outcome, fallback/escalation and verification evidence. A metric such as first-pass verification or human intervention is shown only when it is deterministically available from current records. Otherwise expose it as unavailable/unknown rather than adding a new tracing system merely to fill the report.

4. **Primary positive evidence is verified R2 completion without frontier escalation.** This is evidence that the current R2 path worked for that concrete execution and its recorded task-family/rubric context. It is not a universal statement about all similar work.

5. **Escalation remains a path, not a label.** `R2 -> R3 -> success` must preserve the balanced attempt and the final success. Report an escalation reason only when current provenance records it truthfully; otherwise reason = unknown.

6. **Direct R3 success is not counterfactual evidence.** It does not prove that R2 would fail, and it must not be labeled over-routing automatically. Counterfactual replay remains a later experiment, not a prerequisite.

7. **Sample adequacy is visible at every useful level.** Always show counts/coverage. A global sample may be usable while a task family is still insufficient. Breakdowns are descriptive when small and must not become confident tuning advice.

8. **Keep the first version observational.** No new `ok / weak / overkill` capture unless implementation can prove it reuses an existing state surface with effectively zero lifecycle cost. Default scope is no new human-feedback storage.

9. **Policy changes remain explicit managed changes.** The calibration report can state a concrete candidate adjustment or `no change`, but cannot edit `start_tier_routing.py`, `.dev-platform.toml`, create a Backlog task, or dispatch remediation.

## Suggested surface

Prefer one subcommand under the existing owner, for example:

`python3 scripts/model_routing.py routing-calibration`

Its output should be human-readable by default and machine-readable only if the existing CLI conventions make that cheap. Do not create a dashboard.

## Risks and mitigations

- **Selection bias / uneven families:** expose counts and coverage per family/rubric/provider-model generation.
- **Historical/legacy records:** include only facts each record actually supports; legacy absence is missing evidence, not zero.
- **Gaming cheap-model share:** pair frontier exposure with verification, escalation/fallback, abnormal outcomes and human-intervention signals where available.
- **Overfitting to a short model generation:** preserve `rubric_version` and model/provider provenance and avoid collapsing incompatible generations.
- **False precision:** use bounded descriptive rates/counts, not statistical confidence claims the sample cannot support.
