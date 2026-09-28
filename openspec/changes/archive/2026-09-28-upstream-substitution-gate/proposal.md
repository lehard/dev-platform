## Why

Dev Platform already gates external *agent runtimes* through a compatibility pilot that ends in one bounded decision (`agent-runtime`). No accepted contract covers external *infrastructure tooling*: tools that sync skills, rules, hooks, MCP or model profiles, store team learnings, index codebases, or provide analytics dashboards. Such tooling can overlap Dev Platform's own capability, friction, context and routing code. Without a gate, the choice defaults either to keeping our own code because it exists or to adopting an upstream on its feature claims. Either default can leave two competing sources of truth.

## What Changes

- Add an `upstream-substitution` capability spec. It generalizes the runtime pilot vocabulary to any external agent-infrastructure upstream, and its unit of decision is one overlapping capability.
- Require pilots on the exact current stable release in an isolated, disposable sandbox with mutating upstream defaults disabled.
- Define the required decision evidence, including a measured maintenance-surface baseline and the concrete retirement or justified retention of own code.
- Define adoption constraints: an opt-in pinned capability or adapter, delivery only through an immutable release and controlled rollout, retirement of the superseded mechanism, and a documented rollback path.
- Fix the non-transferable ownership core.
- Add `docs/engineering/upstream-substitution.md` as operating guidance, plus one pointer row in the `AGENTS.md` concern table.

## Impact

This is a specification and documentation change only. No upstream is installed or integrated, `agent-runtime` behavior is unchanged, and no managed-project rendering changes. The follow-up TeamAI pilot for the same Requirement is authored against this contract.
