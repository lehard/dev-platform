# Verification: System One / Jev decision-layer pilot

OpenSpec-Verify: PASS
Verification-Method: manual equivalent completeness/correctness/coherence review against the accepted proposal, design, delta specification and the exact pilot evidence (no `/opsx:verify` tool integration available in this environment), plus `openspec validate pilot-system-one-decision-layer --strict --no-interactive` and the full platform test suite via `scripts/run_test_groups.py --all`
Automated-Checks-Evidence: automated-checks.json

`PASS` verifies that the bounded pilot was executed and reported according to its accepted contract (proposal/design/tasks/spec delta). It does not mean the atomic-judgment pattern or Jev is production-ready: the evidence-backed pilot decision is `watch-only`.

## Automated validation

Executed in the assigned worktree on branch `agent/pilot-system-one-decision-layer`:

- `python3 -m compileall -q template/scripts scripts` -- PASS.
- `python3 scripts/managed_projects.py validate` -- PASS (3 managed, 7 candidate, 3 excluded).
- `python3 scripts/run_test_groups.py --all` -- PASS, 863/863 across 13 groups, `failed_groups: []`.
- `python3 template/scripts/openspec_lifecycle.py check` -- `OpenSpec lifecycle hygiene: OK`.
- `openspec validate pilot-system-one-decision-layer --strict --no-interactive` -- `Change 'pilot-system-one-decision-layer' is valid`.
- `python3 scripts/check_docs_links.py` -- `Documentation link/anchor check: no problems found.`
- `git diff --check origin/main` -- no whitespace errors.

No template/scripts or scripts code was changed by this pilot; only `openspec/changes/pilot-system-one-decision-layer/**` content was added. The full protected suite was still run (not a bounded `select_checks.py` subset) because, like the `validate-ouroboros-execution-backend` precedent, this is a durable decision artifact worth the stronger evidence bar even though it ships no runtime code.

## Completeness

PASS.

- **Judgment schema and taxonomy:** `pilot-evidence/judgment-taxonomy.json` defines a versioned, provider-neutral 15-item taxonomy (5 deterministic, 10 model-judged), matching proposal.md's "bounded набор примерно 15–25" and design.md decision 1 (no `Noul/Choice/Score` leakage -- the schema is plain JSON).
- **Five replay cases:** `rollback-empty-managed-start-transactions` (bounded bug/recovery), `validate-ouroboros-execution-backend` (capability/process-change), `preflight-completion-before-validation`, `add-deepseek-harness-runtime-adapter`, `support-exact-pr-continuation` -- reconstructed from their exact implementing commit with preserved task/spec/diff/verification evidence, satisfying the "at least 5, including one bug/recovery and one capability/process-change case" acceptance criterion.
- **Independent reference verdicts:** `pilot-evidence/cases/<case>/reference.json` records the orchestrating session's own verdict for each of the 10 model-judged items, written *before* the model-adapter arm ran (verified by conversation/tool-call order), so no ground truth was inferred from a compared backend's own output (design.md decision 5).
- **Deterministic arm:** `pilot-evidence/cases/<case>/deterministic.json`, computed programmatically from `tasks.md`/`verification.md`/`automated-checks.json`/`.managed-task.json` with no model involved (design.md decision 2).
- **Model-adapter arm:** one fresh-context subagent per case via the Agent tool (`general-purpose`, explicitly instructed read-only, no access to reference verdicts), answering all 15 judgments in strict typed JSON with verdict + confidence + rationale. `pilot-evidence/cases/<case>/model-adapter.json`.
- **Jev arm:** `pilot-evidence/jev-unavailable.json` honestly records `unavailable` with a specific limitation (no credentials/SDK/network access in this environment, confirmed explicitly by the user; no existing repository integration found) rather than silently skipping it or fabricating a result.
- **Metrics:** `pilot-evidence/aggregate-metrics.json` records overall/subset accuracy, false-allow vs. false-escalation counts separately (0 vs. 3), schema/typed-output reliability (5/5), confidence-calibration signal, and latency/token cost from the Agent tool's own truthfully exposed `<usage>` block (not fabricated, not guessed).
- **Single decision:** `pilot-report.md` records exactly one current decision (`watch-only`) with its evidence and a concrete, event-based activation/revisit criterion (Jev access being provisioned), not a calendar date.

## Correctness

PASS.

- The reference verdicts were spot-checked against the real diff, not only against the narrative evidence documents, for at least one specific claim per case (documented inline in each `reference.json` rationale) -- e.g. confirming `_managed_start_left_no_task_state` and `_continue_exact_pr_from_local_descendant` actually exist in their respective diffs at the described call sites.
- `git status --short` was checked after each of the 5 model-adapter subagent runs and confirmed no file outside `pilot-evidence/` was touched, verifying the attested `write_access: false` rather than trusting the self-report.
- The 3 false-escalation disagreements and 5 near-miss score disagreements are individually listed in `pilot-report.md`'s Results section with case, judgment, both values, and classification; no disagreement was excluded from the reported metric.
- `aggregate-metrics.json`'s risk-direction classification (`RISK_DIRECTION` mapping in the now-removed `aggregate_metrics.py`) was applied consistently to `security_sensitive_surface_touch`, `migration_config_release_impact`, `suspicious_scope_expansion`, `suspicious_large_or_unrelated_diff`, `verification_contradiction`, `human_review_recommended`, and `scope_respected` (inverted, since `false` is the risky direction there) -- verified by manual cross-check of the 3 recorded false-escalation rows against this mapping.
- Latency and token counts in `pilot-report.md` are copied verbatim from each Agent tool call's own `<usage>` block, not estimated.

## Coherence

PASS.

- No production code, orchestration service, event store, or transcript warehouse was added; the only executable artifacts (`deterministic_checks.py`, `aggregate_metrics.py`) were disposable pilot glue and have been removed per design.md decision 10, since the decision is `watch-only`, not `proceed-to-shadow`.
- No live gating, auto-merge-on-confidence, verification/publication/routing change, or downstream rollout was performed or enabled; `pilot-report.md`'s Decision section states this explicitly.
- Jev/System One was not made a required Dev Platform dependency; the repository contains no Jev-specific code, config, or types after this change (only the honest `unavailable` evidence record).
- The full prompt/transcript of each model-adapter subagent invocation was not persisted -- only the bounded structured JSON verdict, confidence, rationale and usage metrics were kept, matching the design constraint against storing full private transcripts when bounded structured evidence suffices.
- `specs/decision-layer-evaluation/spec.md`'s three ADDED requirements (no gating/write authority, deterministic-vs-model separation, single bounded decision with separated error classes) are all reflected in how this pilot was actually conducted, not just declared.

No material divergence remains between the proposal, design, delta requirements, task checklist, and pilot report.

## Acceptance evidence (commands run from the task worktree)

- `python3 -m compileall -q template/scripts scripts` -- pass (exit 0).
- `python3 scripts/managed_projects.py validate` -- `Managed project registry: OK (3 managed, 7 candidate, 3 excluded)`.
- `python3 scripts/run_test_groups.py --all` -- `DEV_PLATFORM_TEST_AGGREGATE ... "failed_groups": [], "group_count": 13, "outcome": "success"`; `DEV_PLATFORM_TEST_COVERAGE ... "declared_test_count": 863, "discovered_test_count": 863, "missing_from_groups": [], "declared_but_not_discovered": [], "duplicated_tests": []`.
- `python3 template/scripts/openspec_lifecycle.py check` -- `OpenSpec lifecycle hygiene: OK`.
- `openspec validate pilot-system-one-decision-layer --strict --no-interactive` -- `Change 'pilot-system-one-decision-layer' is valid`.
- `python3 scripts/check_docs_links.py` -- `Documentation link/anchor check: no problems found.`
- `git diff --check origin/main` -- no whitespace errors.

No CRITICAL or WARNING findings remain. The change is verified; archive and publication follow via the managed lifecycle.
