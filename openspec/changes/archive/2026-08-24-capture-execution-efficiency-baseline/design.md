# Design: Runtime-neutral execution efficiency evidence

## Decisions

1. **One provenance path.** Extend the existing routing/execution record and its bounded outcome evidence. Do not add a second database, tracing service, daemon, or transcript store.
2. **Platform time is authoritative for duration.** Record start/end using the platform execution boundary and derive elapsed duration from monotonic/platform-controlled timing where possible.
3. **Usage is evidence, not a guessed completeness target.** Normalize provider/runtime usage only when the current supported interface exposes it. Every optional usage field preserves source/status semantics; unavailable values remain unknown.
4. **Do not conflate cache efficiency with execution efficiency.** Keep input/prompt, cache-read, fresh/computed input, output and total token concepts distinct when the provider semantics support them. Never treat cache-hit percentage alone as the success metric.
5. **Derived token values require an explicit identity.** A value such as fresh input may be derived only when the provider contract guarantees an exact decomposition; otherwise it remains unknown.
6. **Reuse existing outcomes.** Verification result, first-pass verification, retries/escalation/fallback, human intervention and containment/recovery facts remain owned by their current lifecycle records and are referenced/aggregated rather than reimplemented.
7. **Historical compatibility.** Old records without the efficiency fields remain valid input. Missing is not zero.
8. **Baseline before policy.** Collect evidence first. Do not introduce automatic budgets, runtime switching or self-tuning in this change.
9. **Bounded report.** Provide a dependency-light report from existing local/provenance evidence with counts and medians/percentiles only where meaningful; small samples are explicitly insufficient.
10. **Runtime-neutral schema.** No DSH/Cordis-specific identities or types may appear above the runtime/execution adapter boundary.
11. **Lifecycle durability.** Keep the existing routing record in the integration checkout's machine-local `.claude/model-routing/` directory, rather than only in a disposable task worktree, so normal completed-worktree cleanup does not erase baseline observations.

## Initial normalized evidence

The implementation should choose the smallest compatible representation, but it must be able to express:
- execution start/end/elapsed;
- usage fields such as input/prompt, cache-read, fresh/computed input, output and total tokens when authoritative;
- model request/turn count when authoritative;
- explicit source/status/unknown for optional runtime-provided measurements.

No requirement forces every provider to populate every field.

## Risks

- Provider token semantics differ: preserve field/source semantics and avoid forced normalization that changes meaning.
- Metrics collection could become a new state machine: extend existing provenance only.
- Small samples can mislead: surface counts and insufficient evidence.
- Instrumentation can affect execution: keep capture bounded and non-blocking except for malformed platform-owned records.
