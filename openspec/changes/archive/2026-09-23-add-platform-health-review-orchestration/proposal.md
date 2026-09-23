# Proposal: Orchestrate Process and Architecture Health Review as one combined Platform Health Review

## Why

lehard/development-backlog#157 asks for one user-facing "Platform Health Review" rather than two separate, uncoordinated review mechanisms. Process Health Review already has a cloud, weekly-fuzzy-schedule-plus-manual-dispatch trigger (`openspec/specs/agentic-maintenance/spec.md`); a linked prerequisite change (`add-architecture-health-cloud-review`) gives Architecture Health Review an equivalent cloud trigger. Neither review runs together today, and no capability presents them to a human as one combined function.

## Current to target

Today: Process Health Review and Architecture Health Review each have their own independent cloud trigger (or, for architecture health, gain one only via the prerequisite change); a human has to know both exist and check them separately.

Target: a new `platform-health-review` capability defines one combined trigger (schedule + `workflow_dispatch`) that runs both existing reviews together. Each review keeps its own existing content, reasoning, read-only tools, and safe-outputs constraints unchanged; this change only adds the shared trigger that runs them together and marks the pilot scope.

## What changes

- Add a new OpenSpec capability, `platform-health-review`, that defines the combined trigger requirement.
- Extend or add a GitHub Actions/gh-aw trigger definition (schedule + `workflow_dispatch`) that starts both the existing Process Health Review job and the (now cloud-capable) Architecture Health Review job for the same run.
- Scope enablement to `lehard/dev-platform` only, consistent with agentic-maintenance's central-pilot-precedes-downstream-rollout rule.

## Success evidence

- A single manual dispatch, and separately the configured schedule, starts both reviews for the same run in `lehard/dev-platform`.
- Each review's own existing advisory/read-only/safe-outputs behavior is provably unchanged (no regression in either review's existing accepted behavior).
- `openspec validate --strict` passes for the new `platform-health-review` delta.

## Constraints and non-goals

This change does not alter what either review evaluates or how it reasons about evidence. It does not define the combined durable report artifact (a separate linked change) or any notification/delivery mechanism (a separate linked change). It does not roll the combined trigger out to any managed downstream repository.

## Delivery scope

A new OpenSpec capability delta (`specs/platform-health-review/spec.md`) plus the trigger wiring in the relevant `.github/workflows/*.md` source(s) and their compiled lock workflow(s). No application/product code changes.
