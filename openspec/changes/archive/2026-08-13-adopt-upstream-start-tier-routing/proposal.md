# Proposal: Adopt upstream start-tier routing

Source backlog issue: `lehard/development-backlog#29`

Depends on: `lehard/development-backlog#5` (`adopt-gh-aw-process-automation`).

## Why

The current routing contract starts every managed task on the strongest provider-local parent and asks that parent to decide whether cheaper execution is safe. Dogfood showed this can over-route ordinary well-specified work to Opus/Sol and consume the scarce strong-model budget before any savings occur.

The platform already has an upstream planning/scouting stage during managed-task authoring: accepted intent is refined, relevant repository context is inspected, and a canonical OpenSpec handoff is produced. Routing v2 should use that stage to recommend the initial execution tier before a coding session starts, while retaining runtime freshness checks, verification and controlled escalation for hidden complexity.

## What Changes

- Replace mandatory strong-parent-first routing with a provider-neutral recommended start tier authored with the managed task.
- Define abstract `R1` economy, `R2` balanced and `R3` frontier tiers; concrete models remain runtime configuration.
- Use `R2` as the default production start tier and require an explicit hard trigger for `R3`.
- Keep `R1` defined but disabled for production recommendation until a later evidence-gated change.
- Show the recommendation in the human-facing Issue title as `[R2]` or `[R3]`.
- Separate execution tier, reasoning effort and assurance/verification depth.
- Replace the full strong-parent routing preflight with a bounded execution-time freshness check that confirms the authored tier or escalates on newly discovered evidence.
- Preserve provider-local delegation as a fallback/secondary capability, not a mandatory entrypoint.
- Reuse truthful execution provenance from #5 and existing verification/lifecycle records; do not add a second telemetry/tracing state machine.

## Impact

- Modified specification: `model-routing`.
- Expected affected surfaces: managed-task authoring package/title, routing record/schema, `.dev-platform.toml` mapping, `scripts/model_routing.py` and dogfood adapter, central/generated agent guidance, routing docs and regression tests.
- Current `AGENTS.md` strong-parent instructions must change as part of this managed implementation, not before it.
