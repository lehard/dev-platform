# System One / Jev decision-layer pilot report

## Decision

**`watch-only`**

The atomic-typed-judgment architectural pattern itself performs well on this bounded sample: a deterministic-first design fully resolves 5 of 15 taxonomy judgments with zero ambiguity, and a general-purpose model-adapter backend reaches 89.3% overall agreement with an independently recorded reference across 5 replay cases (75 labelable judgments), with zero dangerous false-allow errors. That is a genuine, positive signal for the pattern.

However, this pilot cannot evaluate Jev/System One itself: no credentials, SDK, or network access to Jev were available in this environment (confirmed explicitly by the requesting user rather than assumed absent), and the repository has no existing Jev integration to fall back on. The Jev arm is honestly recorded as `unavailable` for all 5 cases. A decision to adopt Jev specifically would be evidence-free, so this pilot does not authorize `proceed-to-shadow` for Jev. The pattern's own promise is real enough that outright `reject-for-now` would overstate a negative that was never actually tested, so this is `watch-only`: revisit once Jev access exists to run the same replay set through the real third arm.

This decision does not change production verification, publication, routing, or lifecycle behavior. No live gating, auto-merge-on-confidence, or downstream rollout is performed.

## Judgment schema and taxonomy

`pilot-evidence/judgment-taxonomy.json`, version 1, 15 judgments:

- **5 deterministic** (source of truth is a file/field read, never a model opinion): `task_checklist_complete`, `verification_pass_recorded`, `automated_checks_outcome_success`, `required_artifacts_present`, `spec_delta_present`.
- **10 model-judged** (genuinely ambiguous semantic properties): `scope_respected`, `suspicious_scope_expansion`, `test_evidence_sufficient` (1-5), `regression_risk` (1-5), `security_sensitive_surface_touch`, `migration_config_release_impact`, `suspicious_large_or_unrelated_diff`, `verification_contradiction`, `human_review_recommended`, `action_recommendation` (accept/review/retry).

No `Noul`/`Choice`/`Score` Jev-specific types were copied; the schema is a plain provider-neutral JSON contract, reused across all three intended arms.

## Replay cases

5 already-completed, already-archived managed changes, reconstructed from their exact implementing commit (each a single squash-merge containing both the code diff and the archive move):

| Case | Category | Commit | Diffstat |
| --- | --- | --- | --- |
| `rollback-empty-managed-start-transactions` | bounded bug/recovery | `8f286ec` | 11 files, +473/-18 |
| `validate-ouroboros-execution-backend` | capability/process-change (a pilot decision record) | `52699d6` | 10 files, +552/-0 |
| `preflight-completion-before-validation` | other | `5675efa` | 12 files, +590/-35 |
| `add-deepseek-harness-runtime-adapter` | other (largest case) | `5e63614` | 21 files, +1909/-11 |
| `support-exact-pr-continuation` | other | `80c84af` | 11 files, +423/-5 |

All 5 are accepted, merged, archived changes -- there is no rejected/failed case in this sample (a real coverage limitation, see Limitations below).

## Methodology

For each case, three pieces of evidence were recorded independently before comparison:

1. **Reference verdict** (ground truth for the 10 model-judged items) -- the orchestrating session read the actual diff (`git show <sha>`) and the change's `proposal.md`/`design.md`/`verification.md`, spot-checked at least one specific verification.md claim against the real diff per case, and recorded a verdict + rationale for each of the 10 model-judged items *before* the model-adapter arm ran, so the comparison stays blind. `pilot-evidence/cases/<case>/reference.json`.
2. **Deterministic arm** (ground truth for the 5 deterministic items) -- `pilot-evidence/deterministic_checks.py` reads `tasks.md`, `verification.md`, `automated-checks.json`, and `.managed-task.json` directly and computes each of the 5 deterministic judgments programmatically, with no model involved. `pilot-evidence/cases/<case>/deterministic.json`.
3. **Model-adapter arm** ("existing cheap general-purpose model adapter") -- one fresh-context subagent per case (Agent tool, `general-purpose`, explicitly instructed read-only), given *only* the canonical input (paths to evidence files + the commit SHA), with no access to the reference verdicts. It answered all 15 judgments in strict typed JSON with a verdict, confidence (0-1), and rationale per judgment. `pilot-evidence/cases/<case>/model-adapter.json`. This reuses the same request -> fresh-context backend -> typed-report protocol already established by `template/scripts/independent_review.py` (`fresh_context_required`, `write_access: false`, `availability: available/unavailable`) rather than inventing a new one.
4. **Jev arm** -- recorded once as `unavailable` with an explicit limitation. `pilot-evidence/jev-unavailable.json`.

After each subagent run, `git status --short` on the task worktree was checked and confirmed no file outside `pilot-evidence/` was touched, verifying the attested `write_access: false` rather than trusting it.

## Results

### Deterministic arm

100% agreement with the reference by construction (it *is* the ground truth for these 5 judgments) and 100% agreement with the model-adapter's own independent answers to the same 5 questions across all 5 cases -- unsurprising, since all 5 replay cases are already-accepted, already-archived changes with complete checklists and PASS verification. This is itself useful evidence: **this bounded sample does not stress-test whether the deterministic arm correctly identifies a *failing* case**, because none of the 5 cases is one (see Limitations).

### Model-adapter arm vs. reference

| Metric | Value |
| --- | --- |
| Labelable judgments scored | 75 (5 cases x 15 judgments, none `unknown`) |
| Overall agreement | **89.3%** (67/75) |
| Deterministic-subset agreement | 100% (25/25) |
| Model-judged-subset agreement | 84.0% (42/50) |
| False-allow / false-safe errors | **0** |
| False-escalation errors | 3 |
| Schema/typed-output reliability | 5/5 cases returned valid, complete JSON on the first attempt |
| Mean confidence when correct | 0.865 |
| Mean confidence when incorrect | 0.696 |
| Mean latency per case | 107.8 s (range 73.8-132.3 s) |
| Mean tokens per case | 91,371 (range 85,831-100,289; total 456,856 across 5 cases) |

Full numbers: `pilot-evidence/aggregate-metrics.json`.

**All 8 disagreements**, none of them false-allow:

| Case | Judgment | Adapter | Reference/truth | Note |
| --- | --- | --- | --- | --- |
| add-deepseek-harness-runtime-adapter | test_evidence_sufficient | 4 | 5 | 1-point score miss |
| preflight-completion-before-validation | test_evidence_sufficient | 4 | 5 | 1-point score miss |
| validate-ouroboros-execution-backend | test_evidence_sufficient | 4 | 5 | 1-point score miss |
| rollback-empty-managed-start-transactions | regression_risk | 2 | 3 | 1-point score miss |
| support-exact-pr-continuation | regression_risk | 2 | 3 | 1-point score miss |
| rollback-empty-managed-start-transactions | security_sensitive_surface_touch | true | false | false-escalation |
| support-exact-pr-continuation | security_sensitive_surface_touch | true | false | false-escalation |
| rollback-empty-managed-start-transactions | migration_config_release_impact | true | false | false-escalation |

Every disagreement is the adapter being *more* cautious than the independent reference (a lower test-sufficiency/regression-risk score would be the dangerous direction; none occurred), or flagging a security/config-impact concern the reference judged unnecessary. Zero cases of the adapter clearing something the reference considered risky. For a decision layer whose stated design constraint is "LLM confidence is never the sole criterion for permitting a dangerous action," this observed error skew (conservative, not permissive) is the safer failure mode, though 5 cases is too small a sample to treat this as a proven property rather than a favorable data point.

Calibration is directionally sound at this sample size: mean confidence was higher when correct (0.865) than when incorrect (0.696), though 5 cases x 15 judgments is far too small for a real calibration curve -- this is a directional signal, not a validated property, as the design requires being explicit about.

### Jev arm

Unavailable for all 5 cases. No credentials, SDK, or documented integration exist in this environment or repository. See `pilot-evidence/jev-unavailable.json`. **No comparison between the general-purpose adapter and Jev was possible**, and none is claimed here.

### Judgments better expressed as deterministic logic

The 5 deterministic judgments were, by design, never candidates for the AI layer -- the pilot confirms the underlying design principle (checklist/PASS-marker/outcome-field/artifact-presence/spec-presence are exact file reads, not opinions) rather than discovering it. No *additional* model-judged item in this sample showed a pattern of being trivially reducible to a deterministic check; all 10 required genuine reading of diff content against stated scope, none of which has a single authoritative field to read.

### Coupling / maintenance burden

Total pilot-scoped code: `pilot-evidence/deterministic_checks.py` (~90 lines) and `pilot-evidence/aggregate_metrics.py` (~140 lines), both disposable. No production code, no new orchestration service, no persistent adapter, no event store. The model-adapter "backend" is not a script at all -- it is a fresh subagent invocation through the existing Agent tool, so there is no separate adapter codebase to maintain for that arm. Reusing `independent_review.py`'s request/report shape (rather than inventing a new one) kept the schema design itself small. If a Jev arm were later added, its adapter would be the only genuinely new coupling surface, and design.md decision 1 already requires it stay behind the same provider-neutral schema with no `Noul/Choice/Score` leakage.

## Limitations of this bounded sample

- **No failing/rejected replay case.** All 5 cases are accepted, archived, PASS-verified changes. The taxonomy's ability to correctly flag a genuinely problematic change (a real negative) is untested here; every "risk" judgment in this sample is a matter of degree (e.g. security-adjacency, review-worthiness) on changes that were, in the end, accepted correctly.
- **Reference verdicts were recorded by the same orchestrating session that designed the taxonomy**, not a separate human reviewer -- genuine human-labeled ground truth was out of scope for this bounded pilot; the blinding that was preserved is between the reference and the model-adapter arm, not between the taxonomy author and the reference author.
- **Jev is entirely unevaluated.** Every metric above describes the general-purpose-adapter arm only; nothing here says anything about Jev's quality, cost, or fit.
- **5 cases is a small sample** for the calibration and false-allow/false-escalation claims; they are directional, not statistically validated.

## Activation / revisit criterion

Reconsider only when Jev/System One API or SDK access is actually provisioned for this environment (allowlist grant). At that point, replay the same 5 cases (`pilot-evidence/cases/*/input.json` already identifies the exact commits and evidence paths) through a real Jev arm using the identical taxonomy and canonical input, and compare against the same reference verdicts recorded here. A `proceed-to-shadow` decision for Jev specifically would then require: Jev reaching at least the general-purpose adapter's 89.3% agreement and zero-false-allow result on this same sample, schema/typed-output reliability at least as high, and a concrete Dev Platform maintenance responsibility it could retire or avoid (per design.md decision 6) -- consistent with the bar set by the `validate-ouroboros-execution-backend` precedent.

Until then: no live gating, no auto-merge on confidence, no change to R1/R2/R3 routing, and no downstream rollout.
