# Proposal: Add a bounded project context pack

## Why

Dev Platform already keeps repository-wide agent guidance bounded and uses progressive disclosure for workflow concerns. Managed projects still lack a standard project/domain knowledge layer, so agents reconstruct product semantics, ambiguous terms, architecture invariants, anti-patterns, and representative examples from scattered repository evidence.

The platform should add a project-owned context pack that improves task understanding without turning stable project knowledge into another always-on prompt or duplicating existing rules, checks, OpenSpec, or detailed documentation.

## What Changes

- Define a project-owned `docs/context/` surface with a small entrypoint plus bounded product, domain, architecture, anti-pattern, and example context.
- Keep `AGENTS.md` as a bounded router and load project context only when a task reaches the relevant concern.
- Add targeted OpenSpec context routing instead of requiring every artifact to ingest the whole context pack.
- Define an evidence-first bootstrap/interview flow: inspect repository evidence first, draft only supported facts, and ask a human one unresolved question at a time without inventing missing knowledge.
- Keep raw interview/source material machine-local and preserve project-owned context across Copier updates.
- Use semantic review metadata such as owner/last-reviewed where metadata is useful.

## Capabilities

### Added Capabilities

- `project-context`: managed repositories can maintain and progressively disclose bounded project/domain knowledge for coding agents.

## Impact

- Root/template agent instruction routing.
- Managed-project template and project-owned preservation rules.
- OpenSpec configuration guidance.
- Focused context bootstrap/interview documentation or helper surface.
- Contract/render evidence proving relevant context is discoverable without becoming universal prompt cost.
