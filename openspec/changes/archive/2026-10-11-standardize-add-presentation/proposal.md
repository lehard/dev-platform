## Why

BR-581: the platform already defines ADD as a bounded delta (`openspec/specs/agent-workflow`: ADD records only new or changed consequences, references existing constraints, exposes only unresolved consequential choices, approval is bound to the content digest). The gap is practical behaviour and presentation: agents can restate a detailed Business Requirement as a list of "architecture decisions", an ADD and a free-form report about it are hard to tell apart from a BR retelling, and different agents give the human differently shaped messages, so the human must work out which questions are really open and whether an earlier approval is still valid.

## What Changes

- Extend the canonical `add-intents` capability Markdown (and its template mirror) with the content-boundary judgement: where BR-defined product behaviour, an existing authoritative technical contract, a real ADD delta, OpenSpec-level detail and a genuinely open product question each belong; the key test question; four contrasting examples; and the rule that classification is the agent's evidence-first judgement, not a keyword or category gate.
- Add `add_intents.py render-add <add-path> --requirement owner/repo#N`: a read-only, deterministic projection of the current ADD into the standard Russian structure (header and state, 2–4 sentence summary, delta table, preserved, questions, risks and next step). It writes nothing and creates no second document.
- Compute the displayed state only from existing facts: structural validity, open choices and contradictions, `approved` plus the digest-bound receipt, and freshness. A stale or unprovable approval renders as "требует актуализации", never "утверждён".
- Allow compatible optional fields on existing ADD entries (element `current`, `rationale`, `impact`, `refs`; unresolved choice `kind` of `architecture` or `product`, `options`, `recommendation`) so the projection can show them; absent fields shorten the output and are never invented.
- Point `docs/engineering/agent-workflow.md`, `engineering-capabilities.md` and the `AGENTS.md` concern map at the one standard so every agent route and managed project reads the same text.

## Capabilities

### Modified Capabilities

- `agent-workflow`: new requirements for the ADD content boundary and for the standard read-only ADD projection.

## Impact

`dev-platform/capabilities/add-intents.md` (+ `.toml` hash, template mirror), `template/scripts/add_intents.py` (single implementation, adapter unchanged), `dev-platform/evals/add-intents-pilot.json` (+ mirror), `docs/engineering/{agent-workflow,engineering-capabilities}.md` and template counterparts, `AGENTS.md` / `template/AGENTS.md.jinja` pointer, tests. No change to the ADD/intents/handoff schema versions, `approve-add`, `decompose`, `validate-*`, orchestrator stages, Requirement format, routing or lifecycle.

## Non-goals

BR-338 final report; any new lifecycle or approval gate, semantic or LLM validator, ADR/decision registry, stored second report, UI or per-project setting; whole-repository rescans; changing how pre-authoring depth is selected.
