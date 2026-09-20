# Project context map

This directory is project-owned, reviewed context for stable knowledge that
helps an agent understand this repository's product and implementation. It is a
map, not an always-on prompt: read it only after work reaches a listed concern,
then open only the focused document that applies.

## What belongs here

Add concise, evidence-backed context only when it will remain useful across
tasks. The following names are optional conventions, not mandatory empty
templates:

| Reached concern | Focused context to add or consult |
| --- | --- |
| Product goals, users, key scenarios, or product invariants | `product.md` |
| Project vocabulary, entities, rules, and source-of-truth boundaries | `domain.md` |
| Architecture invariants, decisions, and links to canonical designs | `architecture.md` |
| Approaches that have repeatedly failed or must be avoided | `anti-patterns.md` |
| Small representative implementation paths or fixtures | `examples.md` |

Link to authoritative owners instead of copying them: engineering rules and
checks stay in `docs/engineering/project-rules.md` and check configuration;
accepted behavior stays in OpenSpec; module constraints stay in module
`AGENTS.md`; detailed runbooks and designs stay in their existing documents.

## Bootstrap or refresh

Preserve any non-empty reviewed context. Before adding or changing it, list
the likely evidence-bearing sources, then inspect the relevant ones:

```bash
python3 scripts/project_context.py inventory
```

This helper lists paths but never infers facts or writes a draft. Review the
README, project rules, OpenSpec specs and active changes, relevant code and
checks, and existing documentation.
Distill facts supported by that evidence, with links or concise source notes
where they help later review.

If a material product, domain, or architecture fact remains unresolved after
that inspection, ask one bounded human question at a time; the helper formats
exactly one only after the agent confirms the gap:

```bash
python3 scripts/project_context.py question product
```

Keep an unanswered item explicitly `TODO` or `Unknown`; do not promote a
plausible inference into canonical context. Treat exports, copied tickets,
transcripts, and other raw source material as temporary machine-local input.
Do not commit it to this directory; commit only reviewed distilled context.

When ownership or review cadence matters, use lightweight metadata such as
`owner` and `last-reviewed`; a Git modification time is not evidence that a
fact is still valid.
