# Design: Architecture evidence without autonomous refactoring

## Decisions

1. **Capability mechanics come from #87.** Identity, provenance, project opt-in, provider-local materialization, update and removal are inherited from the shared optional-capability lifecycle.
2. **Separate concern from Process Health.** Process review evaluates workflow friction; Architecture Health evaluates code/design structure. Reports may cross-reference evidence but do not share a state machine.
3. **Read-only by default.** Review cannot edit code, publish Issues or create managed tasks.
4. **Evidence before proposals.** Findings identify exact files/modules/interfaces and distinguish observations, uncertainty and suggested improvements.
5. **No vanity score.** Do not collapse architecture into one numerical score until such a metric has demonstrated decision value.
6. **Alternative design is selective.** For significant interface/subsystem decisions, a bounded `design it twice` mode can compare genuinely different options; ordinary changes do not require it.
7. **Human promotion.** Any accepted refactor or architectural change enters the normal Discuss/Backlog/OpenSpec lifecycle separately.
8. **Upstream as reference.** `improve-codebase-architecture` and `codebase-design` inform heuristics but are not authoritative workflow owners.
