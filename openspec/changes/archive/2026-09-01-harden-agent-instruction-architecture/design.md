# Design: Bounded instruction maps with explicit cross-surface mechanics

## Decisions

1. **Existing sources stay authoritative.** `AGENTS.md`, OpenSpec, canonical engineering docs, and the ChatGPT Project adapter keep their current ownership; no new instruction hierarchy is introduced.
2. **Bounded always-on context.** Root/tool-facing maps contain triggers, invariants and destinations, not copied workflow manuals.
3. **Explicit pointers.** A concern-specific document must be discoverable from a concrete trigger or task concern, not only from tribal knowledge.
4. **Single semantic owner.** Shared lifecycle semantics have one authoritative owner. Tool/runtime-specific documents describe only the mechanics that genuinely differ.
5. **Semantics and mechanics are distinct.** `Discuss`, fixation, quick execution, managed execution, canonical managed representation, and STOP rules are shared. ChatGPT Project may publish through connected GitHub mutations because it has no repository checkout; repo-local Codex/Claude use `managed_task.py` because they do.
6. **No ChatGPT-only task format.** A task authored by ChatGPT must be consumable by the normal `start_managed_task.py` importer without a special translation path.
7. **Repo-local deterministic helper remains preferred.** The existence of connector-based ChatGPT authoring is not a reason to make Codex/Claude manually reconstruct GitHub/package mechanics when the local helper is available.
8. **Evidence proportional to risk.** Structure/link/render checks are standard; bounded behavior tests cover discovery plus representative ChatGPT/repo-local authoring equivalence.
9. **Upstream as reference.** `writing-for-agents` informs the audit but is never a runtime dependency or policy owner.

## Compatibility and rollout

The central repository and the Copier template receive the same quality
contract and ChatGPT adapter. New rendered projects receive the new
platform-owned documents and root-map pointers. Existing projects preserve
their project-owned root `AGENTS.md` through Copier's `_skip_if_exists` policy,
so this change does not silently overwrite local guidance or promise a retrofit
of its pointers. Existing projects can adopt the new docs through their normal
reviewed update path.

The new tests use local fixtures and the existing managed package parser. They
do not call a ChatGPT service, create a real Issue, or require the upstream
reference at execution time. This keeps authoring compatibility evidence
deterministic while exercising the same package shape that normal intake reads.

## Risks and mitigations

- **A root-map pointer could name a document missing from a rendered project.**
  Keep central and template destinations paired, and exercise documentation
  links plus every supported template profile.
- **ChatGPT guidance could drift into a parallel task format.** Require the
  normal package marker, manifest fields, artifact blocks, and discovery parser
  in fixture evidence.
- **Thin adapters could grow a copied lifecycle.** Bound their line count and
  assert that they point to `AGENTS.md` without authoring-rule text.
