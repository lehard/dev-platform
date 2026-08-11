## Context

The source PR must be merged before a release tag can accurately identify its
history. `publish-version.yml` publishes a tag only after a `VERSION` change is
merged on `main`, then dispatches `rollout.yml` with that exact tag.

## Decisions

1. Use the next SemVer patch version `1.4.26`; `v1.4.25` already exists and
   `v1.4.26` is absent from origin.
2. Deliver the version bump through the normal managed source PR lifecycle;
   do not create or move a release tag manually.
3. Complete semantic verification and archive the OpenSpec change in the
   release PR before it is published, as required by the platform lifecycle.
   Once that PR merges, `publish-version.yml` is the authoritative release and
   rollout executor; evidence from that external execution is recorded on the
   Development Backlog issue rather than by reopening an archived source
   change.
4. Treat rollout PR creation as delivery. Downstream PR review and merge stay
   with each target repository's normal protection and are never automated here.
5. If the release or a managed target is blocked, retain its exact GitHub URL
   and workflow diagnostic; do not retry by changing target ownership, using a
   personal token, or consuming mutable `main`.
