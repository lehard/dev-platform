# Verification: selective domain interrogation

## Semantic review

Completeness: all 12 OpenSpec tasks are complete. The capability is a canonical descriptor
(`dev-platform/capabilities/selective-domain-interrogation.toml`) plus a hash-pinned instruction
file and a deterministic eval fixture. It reuses the existing #87 optional engineering capability
lifecycle for identity, provenance, opt-in (`dev-platform/capabilities.toml`), provider
materialization, update and removal; it adds no registry, config schema, provider-copy path, or
second task state machine. `capabilities.toml` stays opt-out by default.

Correctness: the instruction requires establishing domain context from bounded repository/provided
evidence first, classifying each candidate ambiguity as repository-resolvable or a genuine
product/intent choice, resolving the former from evidence without a user question, and surfacing
only unresolved choices that would materially change the intended outcome. Accepted decisions are
routed into the existing `proposal.md`/delta specs/`design.md`/`tasks.md`; a `CONTEXT.md`, ADR
ledger, status log, second backlog, or parallel plan is explicitly disallowed, and the materialized
OpenSpec package remains the single canonical implementation contract. A sufficiently clear task
gets no interrogation ceremony. The deterministic fixture covers ten materially-ambiguous /
domain-heavy triggers and ten hard negatives for sufficiently clear tasks (20/20 pass, distribution
30 triggered / 30 not-triggered), and its three objective comparisons verify the pre-implementation
material-choice detection, the evidence-first no-question control, and the clear-task exemption.

Coherence: the canonical descriptor/instruction/fixture, the Copier template copies, the
`engineering-capabilities.md` guidance (source and template mirror), `tests/test_capability_manager.py`,
and `tests/test_template_contract.py` all follow the existing optional-capability conventions. The
reviewed upstream `grill-with-docs` is pinned in the guidance (commit `6654f6b6...`, blob
`62b9efb6...`, MIT); no upstream files are vendored or fetched at runtime, and its inline
`CONTEXT.md`/ADR-ledger and delegate-the-loop behaviors are explicitly rejected.

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review against proposal (outcome + success criteria), delta spec, design, tasks, descriptor/instruction, deterministic eval fixture, and focused capability/template checks plus the full platform test suite.
Automated-Checks-Evidence: automated-checks.json
