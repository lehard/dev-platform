# Design: Final operator-neutral public identity

## Context

The new public repository will be initialized from a deterministic sanitized snapshot. #122 proved that snapshot as a self-contained source tree, but two kinds of migration knowledge still live in shipped source: one concrete operator backlog identity and a private-name denylist used to ensure old downstream compatibility traces do not leak.

Those are useful during migration but are not product behavior. Keeping them in the fresh source would defeat the purpose of separating public core from operator installation.

## Decisions

1. **Canonical source is product identity; companion operator repositories are not.**
   The product may refer to its own canonical public source where a real install URL is required. Development Backlog, fleet registry, bot identity, Project number, and downstream repositories are operator state.

2. **Synthetic evidence for optional integrations.**
   Tests/specs/examples use `example-org/development-backlog`, `example-org/example-service`, or values supplied by fixtures. They verify contracts, not the maintainer's installation.

3. **Two sanitizer layers, one candidate set.**
   Reusable sanitizer code remains public and owns candidate selection, secret checks, prohibited-path checks, source completeness, and generic repository-identity rules. An external one-shot cutover policy can add extra deny repositories/markers. Audit and snapshot still consume exactly the same candidate set.

4. **External policy is data, not a plugin framework.**
   Use the smallest deterministic schema needed for migration (for example version plus bounded lists of prohibited repository strings and compatibility regex/literal markers). Do not create a generalized policy engine or long-lived plugin system.

5. **Private deny values never enter snapshot evidence.**
   Receipts may record policy schema/version and digest, but not the private deny strings themselves. Diagnostics use class/path where practical. The policy path/value source remains outside the public candidate.

6. **No split-literal concealment in shipped code.**
   The fresh public sanitizer must not reconstruct private project names in source merely to avoid matching itself. Old private markers exist only in external migration input.

7. **Keep #122 completeness guarantees.**
   Tests, accepted OpenSpec specs, CI, eval fixtures, and source-completeness smoke remain part of the canonical snapshot. This task does not solve identity leakage by excluding verification surfaces again.

8. **Operator configuration remains local/external.**
   The current maintainer's Development Backlog, registry path, bot identity, and legacy fingerprints are configured outside the repo. The task documents the exact required key set and validation sequence but does not manufacture values that cannot be derived safely from repository evidence.

9. **Fail closed before real rollout.**
   If required registry or legacy migration continuity data is still absent after public cleanup, operator doctor/rollout reports the blocker. No fallback private defaults are reintroduced into public source.

10. **Admin cutover remains later.**
    Only after final external-policy audit, history-secret audit, and extracted-snapshot smoke are green on one exact revision should the owner create/rename/change visibility of repositories.

## Verification strategy

- Search/contract tests prove the concrete current Development Backlog repository is absent from the public candidate and shipped allowlists.
- Tests/spec fixtures for operator participation use synthetic identities.
- External cutover-policy tests cover valid policy, malformed/missing policy, finding detection, receipt redaction, and proof that the policy file is outside the snapshot.
- A regression test proves private marker values do not occur in shipped sanitizer source.
- Existing snapshot completeness/smoke, history-secret audit, operator isolation, GitLab exact-head, and rollout tests remain green.
- Final audit/snapshot evidence is tied to the exact final source revision.
