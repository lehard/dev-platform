# Selective domain interrogation

Use this capability only when managed work is **materially ambiguous** or **explicitly domain-heavy**, and a wrong reading of the domain would produce a technically clean implementation of the wrong thing. It is a bounded pre-design refinement pass, not a mandatory interview and not a second planning system.

Do not run it for a request whose outcome and domain model are already sufficiently clear for safe authoring or execution: a concrete bounded change, an already-specified field, a mechanical correction, or a task whose terms are unambiguous in context. A clear task does not get an interrogation ceremony. If an apparently clear task turns out to hide a consequential domain choice, stop and run this pass before implementing on an invented assumption.

The upstream `grill-with-docs` pattern informs this approach; it is a reference, not an authoritative runtime workflow dependency, and none of its files are vendored or fetched at runtime.

## 1. Establish the domain context from evidence first

Before forming any question, read the available context that can settle it:

- repository guidance (`AGENTS.md` and module-level `AGENTS.md`), accepted specs under `openspec/specs/`, and any active delta;
- the managed package (`proposal.md`, `design.md`, `tasks.md`, delta specs) and the source issue;
- relevant code, tests, fixtures, data models, and recent history;
- domain documents the user or repository explicitly provided.

Prefer a named subsystem or the change hotspot; do not scan the whole repository by default. Record only what you consulted and what it settled, in bounded form — no reasoning transcript.

## 2. Separate evidence-resolvable facts from genuine product choices

For each candidate ambiguity, classify it:

| Field | Required content |
| --- | --- |
| Ambiguity | The unclear term, hidden assumption, or unstated decision. |
| Resolvable from | The authoritative evidence that answers it, or `none found`. |
| Resolution | The value the evidence establishes, when evidence exists. |
| Materiality | How the intended outcome changes if this is decided wrong. |

A **repository-resolvable** ambiguity is closed by reading the evidence. Do not turn it into a user question. Record the resolution and the source.

A **genuine product/intent choice** remains only when available evidence cannot settle it **and** deciding it wrong would materially change the intended outcome. Anything that is neither material nor unresolved is not worth raising.

## 3. Ask the human only for unresolved material choices

Surface a short list of the remaining material choices, each with the options you see and the consequence of each. Ask before implementation proceeds on an assumption. Do not:

- ask about facts the repository already answers;
- invent new product requirements or silently pick one for the user;
- expand scope beyond the managed task's stated intent and non-goals;
- block a task that has no unresolved material choice.

If the user is unavailable, record the open choice and the safest bounded interpretation rather than guessing at a consequential one.

## 4. Route accepted decisions back into the existing OpenSpec artifacts

Fold each resolved decision into the artifact it belongs in:

- goal or scope clarified -> `proposal.md`;
- observable behavior clarified -> delta specs;
- technical approach or domain model clarified -> `design.md`;
- task order or dependency clarified -> `tasks.md`.

Do not create a `CONTEXT.md`, an ADR ledger, a status/decision log, a second backlog, or a parallel plan. The materialized OpenSpec package remains the single canonical implementation contract; this pass only makes it correct before code is written.

## Representative shape

For a task to "add tiered pricing", a useful record is: the term "tier" is resolved from an existing `billing/plans.py` enum (repository-resolvable, not a question); whether tiers stack with per-seat pricing is not answered anywhere and changes the invoice total (material) — surfaced to the user; the resolved stacking rule is written into `design.md` and the delta spec. No new context file is created, and a separately requested "clarify the button label" item is dropped as immaterial.
