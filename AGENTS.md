# Developer Platform Agent Rules

This repository is the central source of truth for reusable engineering process shared by multiple software projects. Treat changes here as potentially cross-project.

## Sources of truth

- `AGENTS.md` — how agents work in this repository.
- `openspec/changes/<change>/` — what is being changed now for non-trivial platform work.
- `openspec/specs/` — durable expected behavior after OpenSpec changes are archived.
- `docs/` — durable platform architecture, adoption and operational guidance.
- `template/` — rendered downstream project contract.

Do not create a second backlog or duplicate implementation plan for work already represented by an active OpenSpec change.

## Scope discipline

Promote a rule/tool into this repository only when it is genuinely reusable across projects or across a defined project profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project.

A change that modifies a downstream managed file must consider both:

1. new-project behavior;
2. update behavior for existing projects with local project-owned extensions.

Prefer additive or merge-friendly evolution. Avoid silently deleting downstream content.

## Development workflow

For non-trivial changes, use OpenSpec before implementation. Fix shared contracts before parallelizing implementation.

Keep platform tooling dependency-light. Core project scripts rendered from `template/scripts/` should use the Python standard library unless a dependency is explicitly justified.

Validate at least:

```bash
python3 -m compileall -q template/scripts
python3 -m unittest discover -s tests -v
```

When Copier is available, also render the template into a temporary directory and run the generated doctor.

## Platform-owned vs project-owned files

Platform-managed files should contain reusable process only. Project-specific rules belong in `docs/engineering/project-rules.md`, module-level `AGENTS.md` files, OpenSpec specs/changes, or other project-owned docs.

Do not put secrets, SSH details, production credentials, personal data or machine-specific paths into the template.

## OpenSpec integration

OpenSpec itself is an external dependency. Do not vendor or fork OpenSpec-generated Claude/Codex skills into this platform. A fresh project may initialize OpenSpec automatically when the CLI exists. Adoption into an existing Git repository must never auto-run an OpenSpec migration: review the repository first and run the printed init/update command explicitly. Platform code owns only the policy around how OpenSpec is used.

## Friction promotion

An isolated problem in one project is not automatically a platform rule. Require evidence that the issue is reusable, recurring, safety-relevant or structurally caused by the shared workflow. Platform improvements should be expressed as an OpenSpec change here and then propagated to projects through reviewed updates.
