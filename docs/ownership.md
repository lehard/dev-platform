# Platform ownership model

`dev-platform` exists to prevent engineering-process drift between projects without turning every repository into an identical clone.

## Platform-owned

The platform owns reusable process contracts and mechanisms:

- root agent workflow;
- OpenSpec lifecycle policy;
- worktree isolation and coordination;
- merge safety;
- check-selection mechanism;
- friction recording/review format;
- reusable CI entrypoint;
- project bootstrap/update mechanics.

These files may be updated by Copier and should remain generic.

## Project-owned

Each project owns its product and implementation reality:

- business/domain requirements;
- architecture choices that are not universal;
- module-specific engineering rules;
- test commands and check mappings;
- deployment/runbook details;
- secrets and machine-local access data.

Project-owned rules belong in `docs/engineering/project-rules.md`, module-level `AGENTS.md`, OpenSpec artifacts, and project-specific docs/configuration.

## Override rule

A project may be stricter than the platform. It should not silently weaken platform safety rules.

If a platform update conflicts with a real project invariant, do not force the update. Resolve the conflict explicitly and, if the invariant is broadly reusable, propose an upstream platform change.
