# Design: Bounded atomic-judgment decision-layer pilot

## Decisions

1. **Provider-neutral judgment schema is canonical.** The judgment taxonomy and schema are defined independent of Jev. System One's `Noul/Choice/Score` types are not copied as canonical domain types where doing so would create vendor leakage; only a minimal provider-neutral judgment schema is kept.
2. **Deterministic checks are the source of truth where they exist.** Where a judgment can be established directly (tests, file existence, exit status, exact version, changed paths), the AI layer does not duplicate it as ground truth; the model is scored only on genuinely ambiguous semantic properties.
3. **Same canonical input, up to three arms.** Each replay case runs through the deterministic/rule baseline where applicable, the existing cheap general-purpose model adapter, and Jev/System One only when its API/runtime is reachable -- so results are comparable rather than backend-specific in their input.
4. **Historical replay, no live risk.** The pilot uses at least 5 already-completed representative managed tasks with preserved task/spec/diff/verification evidence, including at least one bounded bug/recovery case and one capability/process-change case. No new live agent runs are produced for the pilot, and no production task is gated on its output.
5. **Ground truth is recorded, never invented.** Every labelable judgment gets an independently recorded reference verdict, or an explicit `unknown/not-labelable`; the benchmark never fabricates ground truth to fill a gap.
6. **No write access, no gating authority.** The decision model gets no write access to any repository or worktree, and LLM confidence is never the sole criterion for permitting a dangerous action.
7. **Bounded scope, no new infrastructure.** The pilot does not build a new orchestration service, event store, or transcript warehouse; it does not make Jev a required Dev Platform dependency; it does not change merge/release/routing policy; and it does not store full private prompts/transcripts where bounded structured evidence is sufficient for the benchmark.
8. **Coupling is measured, not hidden.** Any Jev-specific type or SDK usage, translation glue, or manual intervention required to run the pilot is recorded as adoption cost, not absorbed as invisible pilot plumbing.
9. **Error classes stay separate.** False-allow/false-safe errors (the decision layer wrongly clears something unsafe) are reported separately from false-escalation errors (the decision layer wrongly stops something safe); they are never averaged into one accuracy number.
10. **Disposable by default.** Prototype/glue introduced for the pilot is removed afterward unless the final decision is `proceed-to-shadow` and the retained seam is demonstrably small, isolated, and useful for the explicitly named next step.

## Decision outcomes

- `proceed-to-shadow`: judgment correctness and the false-allow/false-safe error rate are acceptable on labelable cases, schema/typed-output reliability is high, adapter coupling/maintenance burden is bounded, and at least one judgment class shows enough signal to justify a non-blocking shadow deployment alongside existing verification (still with no gating authority).
- `watch-only`: the atomic-judgment pattern, and/or Jev specifically, work technically but do not yet show enough correctness, calibration, or maintenance-reduction benefit to justify shadow deployment; record the concrete gap and an evidence-based revisit condition.
- `reject-for-now`: correctness (especially false-allow/false-safe errors), reliability, containment, or coupling is unacceptable; record the concrete evidence and an event/evidence-based revisit condition rather than an arbitrary calendar date.
