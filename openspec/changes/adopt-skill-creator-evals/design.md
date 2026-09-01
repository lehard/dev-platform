# Design: Provider-neutral eval core with bounded provider adapters

## Decisions

1. **Capability identity comes from #87.** The eval subsystem consumes canonical capability/skill identity, invocation intent and content provenance; it does not define another store, installation mechanism, or provider-copy ownership model.
2. **Discoverable authoring, invisible plumbing.** The normal UX is a request to create/adopt/update/audit a skill or capability. The #87 management path automatically calls #79's eval decision; users do not need to know an eval skill name.
3. **Static tooling and runtime execution are separate.** Structural validation, packaging helpers, aggregation/reporting, and applicable schemas from `skill-creator` may be reused/adapted independently. Claude-specific runtime logic is reference/provider-adapter material, not canonical core.
4. **Selective live evaluation.** Structural validation runs for every candidate change. New reusable/external capabilities and material trigger/description/instruction/tool/safety changes are automatically considered for live eval. Demonstrably non-behavioral changes may skip with an explicit reason.
5. **Provider-neutral eval records.** Core records candidate identity/hash, eval case, expectation, run count, status/result, bounded evidence, and provider/runtime provenance. Provider event names and command paths do not appear in the canonical schema.
6. **Truthful status taxonomy.** `not-triggered`, `timeout`, `runtime-error`, `unsupported`, and `blocked/unavailable` are distinct outcomes. Tool/runtime failure is never silently counted as a negative trigger.
7. **Supported execution paths only.** Claude and Codex adapters use current platform-supported execution/routing/containment surfaces. The upstream nested `claude -p` pattern is not adopted merely for compatibility with `skill-creator`.
8. **No second orchestrator.** Evals compose existing bounded execution primitives. If provider-neutral live execution would require a new unsafe runtime layer, the task reports an architecture blocker instead of expanding scope silently.
9. **Repeated positive and hard-negative evidence.** Live trigger behavior is sampled across multiple runs because model triggering is nondeterministic; reports expose rates and sample sizes rather than one-run truth.
10. **Outcome value matters.** For objectively verifiable workflows, representative evaluation compares capability-enabled behavior against baseline/no-capability. Subjective output skills may use lighter qualitative evidence when a meaningful objective verifier does not exist.
11. **Sanitized evidence only.** Evals retain the smallest prompts/results/provenance needed for review and never require secrets, private full transcripts, or chain-of-thought.
12. **No autonomous promotion.** Eval output can support a later managed change but cannot publish, roll out, rewrite durable capabilities, or create managed work automatically.
