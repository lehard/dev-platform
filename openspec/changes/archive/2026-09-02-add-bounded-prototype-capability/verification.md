# Verification: bounded prototype

## Semantic review

Completeness: all OpenSpec tasks are complete except the final verify/archive/publish step
this receipt records. The capability is a canonical descriptor
(`dev-platform/capabilities/bounded-prototype.toml`) plus a hash-pinned instruction file
(`bounded-prototype.md`, sha256 `ea8268a6…`) and a deterministic eval fixture
(`dev-platform/evals/bounded-prototype-pilot.json`). It reuses the existing #87 optional
engineering capability lifecycle for identity, provenance, opt-in
(`dev-platform/capabilities.toml`, still opt-out by default), provider materialization, update
and removal; it adds no registry, config schema, provider-copy path, branch, issue, progress
file, status, or second task state machine.

Correctness: the delta adds four requirements to `engineering-capabilities`, each scoped to the
`bounded-prototype` capability by name. The instruction requires the experiment to state its
question, options/hypotheses and time/iteration/cost bounds up front; to run only in a temporary
throwaway workspace or an explicitly declared prototype area; to leave production source,
dependencies, credentials, CI and task state unchanged; to be refused when it would need
unapproved credentials, production writes, sensitive data or wider permissions; to stop and
record remaining uncertainty when bounds are exhausted; to retain only a bounded decision record
with no transcript or secrets; to clean temporary state by default with explicit,
policy-compatible retention only; and never to promote prototype code into production
automatically — a useful result is carried forward as a decision plus evidence and real
implementation enters the ordinary managed OpenSpec lifecycle. A sufficiently clear task, a
mechanical change, or a bounded fix with an established cause gets no prototype step.

The deterministic fixture covers ten positive prompts (including a UI-variant comparison and a
falsifiable technical spike) and ten hard negatives (including a fully specified task and an
experiment that would require live production credentials and real charges); 20/20 cases pass
with distribution 30 triggered / 30 not-triggered, and its three objective comparisons verify
the bounded UI-variant and technical-spike behavior, the clear-task and prohibited-authority
non-triggering, and the default-cleanup / no-automatic-promotion rule.

Coherence: the canonical descriptor/instruction/fixture, the Copier template mirror
(`template/dev-platform/…`), the `engineering-capabilities.md` guidance (source and template
mirror), `tests/test_capability_manager.py` (new `test_bounded_prototype_is_isolated_optional_and_non_promoting`,
setUp copy lists) and `tests/test_template_contract.py` (required-file list plus a new mirror
equality test) all follow the existing optional-capability conventions. No upstream skill file
is vendored or fetched at runtime and no external content is adapted; the guidance records this
explicitly.

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review against proposal (outcome + success criteria), the four-requirement delta spec, design, tasks, descriptor/instruction, deterministic eval fixture (20/20, capability_manager evaluate --runtime fixture), and focused capability/template tests plus the full platform test suite (`scripts/run_test_groups.py --all`).
Automated-Checks-Evidence: automated-checks.json
