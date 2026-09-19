# Design: Project context as a progressive-disclosure layer

## Context

The current platform intentionally keeps `AGENTS.md` bounded and routes detailed concerns to canonical documents. It also preserves project-owned `docs/engineering/project-rules.md` and `openspec/config.yaml`. The missing layer is stable project/domain knowledge that is useful across quick tasks, debugging, design, review, and OpenSpec work but does not belong in workflow rules or accepted behavior specs.

## Decisions

1. **Use `docs/context/`, not `openspec/context/`.** Project/domain knowledge is needed outside OpenSpec, so it must not be coupled to one planning surface.
2. **Make the entrypoint a map, not an encyclopedia.** A small context index routes to product, domain, architecture, anti-pattern, and example concerns; only reached concerns are loaded.
3. **Do not duplicate canonical owners.** Engineering standards/check commands remain in project rules/check configuration, accepted behavior remains in OpenSpec, module constraints remain in module `AGENTS.md`, and detailed architecture/runbooks remain in their existing docs.
4. **Bootstrap from evidence before interviewing.** The agent first reads bounded likely evidence sources, drafts only supported facts, then asks one unresolved question at a time. Unknown stays unknown/TODO.
5. **No raw knowledge dump in Git.** Exported Confluence/SberTrack or similar material is temporary input; reviewed distilled context is the repository artifact.
6. **Preserve project ownership.** Context content must survive Copier updates just like other project-owned surfaces.
7. **Route OpenSpec proportionally.** Proposal/spec/design/task guidance names the relevant context concern rather than injecting every context file globally.
8. **Prefer semantic review metadata.** If files carry metadata, use owner and last-reviewed semantics rather than pretending Git modification time proves the content is still valid.

## Initial context shape

The implementation may adjust exact filenames if existing repository conventions make a smaller coherent shape possible, but it should preserve the conceptual concerns: entrypoint, product, domain, architecture, anti-patterns, and examples. Empty mandatory placeholder files are not a success criterion.

## Verification

Use focused evidence for root-map boundedness, reached-concern discovery, negative unrelated-concern loading, fresh render/bootstrap, existing-project preservation, and OpenSpec targeted routing.
