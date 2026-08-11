## Why

Source backlog issue: `lehard/development-backlog#1`  
Prepared against: `lehard/dev-platform@53b06c072a477b550b085f00e5051b4df7eb70cd`

Non-trivial product and platform work is increasingly designed in ChatGPT before a coding agent is involved. The current dev-platform already provides a strong execution lifecycle once an OpenSpec change exists, but it has no standard intake boundary between a human-visible cross-project backlog and that repository-local OpenSpec lifecycle. As a result, the user must re-explain a planned change to a coding agent, or alternatively put every tiny direct fix through a heavyweight backlog/spec process.

The platform needs two explicit paths: managed tasks for planned, non-trivial work and quick tasks for small changes that are given directly to an agent and executed immediately. A managed task should carry the already-agreed OpenSpec planning package from the central Development Backlog into the target repository without asking another model to rediscover the product decision.

## What Changes

- Introduce a platform-wide distinction between `managed task` and `quick task`.
- Define a versioned `managed-openspec:v1` transport envelope stored with a central Development Backlog issue while the task is still in Backlog. The envelope identifies the source issue, target repository, OpenSpec change name, target `main` commit used during preparation, and the exact OpenSpec artifacts supplied by ChatGPT.
- Add a deterministic managed-task import entrypoint to generated repositories. It fetches the referenced backlog issue using existing GitHub authentication, validates the transport envelope and current target repository, creates the OpenSpec scaffold through the installed OpenSpec CLI/schema, materializes the supplied artifacts, records provenance, and performs structural preflight. It does not start implementation or apply the change.
- Make import idempotent for an unchanged package and fail closed when an existing local change conflicts with a changed package or a different source issue.
- Treat `prepared_against` as freshness evidence rather than a permanent lock: if target `main` has advanced, the importer reports the mismatch and the agent must perform semantic preflight against current specs/active changes before implementation.
- Update root and generated agent guidance so an explicitly referenced Development Backlog issue follows the managed path, while small direct tasks continue through the existing workflow without a central issue or ceremonial OpenSpec.
- Require an agent to stop and propose managed-task escalation when a supposedly quick task expands into a non-trivial product/architecture change instead of silently broadening scope.
- Preserve source-of-truth ownership: before import, the backlog package is the planning handoff; after successful materialization, repository-local OpenSpec is the canonical implementation contract. The backlog issue remains the human task/index and provenance link, not a second implementation plan.
- Keep v1 deliberately manual at the user gate. This change does not watch GitHub Project `Ready`, launch agents automatically, or mutate Project statuses.

## Capabilities

### New Capabilities

- `managed-task-intake`: Versioned, deterministic import of ChatGPT-prepared OpenSpec packages from the central Development Backlog into a target repository.

### Modified Capabilities

- `platform-lifecycle`: Distinguish managed-task intake from quick direct work and require semantic preflight/escalation boundaries before the existing execution lifecycle begins.

## Platform / rollout scope

This is universal platform behavior, not a profile-specific feature. `light`, `standard`, and `multi-agent` repositories may all receive managed-task intake because the importer only prepares OpenSpec planning state and does not own worktree/branch/publication behavior.

The change affects both new projects and existing managed-project updates. New renders receive the helper and guidance directly; existing managed repositories receive them through the normal reviewed Copier update path. Downstream managed files include the generated agent guidance, workflow documentation, the new managed-task helper, and template contract/doctor expectations as appropriate.

## Compatibility and active-change boundaries

The helper must not require a new service, API key, global OpenSpec mutation, or machine-specific path. It should reuse the platform's existing validated GitHub CLI/API authentication and the repository's installed OpenSpec CLI.

Existing mature repositories may already own colliding files. Copier conflict/ownership rules remain authoritative; the rollout must not blindly overwrite project-owned content.

The active `adopt-gh-aw-process-automation` change owns friction/process-maintenance automation and its GitHub Agentic Workflow pilot. This change must not turn managed-task intake into a second cloud scheduler or reuse friction issues as development tasks. The active `durable-publication-recovery` change owns publication recovery. Managed-task intake stops before implementation and must not alter publication semantics.

This first issue is a bootstrap exception: because the importer does not exist yet, the coding agent may manually materialize this package using the current OpenSpec CLI after checking the target repository and active changes. Subsequent managed tasks should use the standard importer.

